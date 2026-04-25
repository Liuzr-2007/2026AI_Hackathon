import os
import re
import sys
import traceback
import subprocess
import requests
import gradio as gr
from datetime import datetime
from dotenv import load_dotenv

# ==================== 后端逻辑 (完全保留，未做任何修改) ====================

load_dotenv()
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

HIGH_RISK_CMDS = [
    "rm -rf /", "rm -rf /etc", "rm -rf /boot", "rm -rf /var", "rm -rf /root",
    "mkfs", "dd of=/dev/", "chmod -R 777 /", "chmod 777 /etc",
    "vi /etc/shadow", "passwd root", "vi /etc/sudoers",
    ":(){ :|:& };:"
]

MEDIUM_RISK_KEYWORDS = ["useradd", "userdel", "kill -9", "chmod ", "chown ", "rm "]

log_entries = []
pending_cmd_state = None

def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    log_entries.append(log_entry)
    print(log_entry, file=sys.stderr)

def get_log_content():
    if not log_entries:
        return "暂无日志记录"
    return "\n".join(log_entries)

def check_security(cmd):
    for bad in HIGH_RISK_CMDS:
        if bad in cmd:
            return False, "BLOCK", f"🚨 安全风控拦截：已触发最高级别预警！拒绝执行高危操作。\n\n命令：`{cmd}`"

    is_medium_risk = any(keyword in cmd for keyword in MEDIUM_RISK_KEYWORDS)
    if is_medium_risk:
        return False, "CONFIRM", f"⚠️ 中等风险预警：该操作属于变更操作，请回复「确认执行」继续。\n\n待执行命令：`{cmd}`"

    return True, "SAFE", "检查通过"

def safe_run(cmd):
    if "useradd" in cmd or "userdel" in cmd:
        cmd = f"sudo {cmd}"
    try:
        timeout = 60 if "find " in cmd else 15
        res = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=timeout, encoding="utf-8")
        return res.strip() or "命令执行成功，无额外输出。"
    except subprocess.CalledProcessError as e:
        return f"终端报错：{e.output}"
    except Exception as e:
        return f"❌ 系统异常：{str(e)}"

def ask_ai_to_plan(prompt, history):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    system = """你是Linux首席运维架构师。
规则：
1. 将自然语言需求拆解为Linux命令
2. 只输出纯命令，无解释、无代码块
3. 如果用户问的是非Linux问题（如天气、闲聊），请回复：[非运维需求]
4. 保持多轮对话上下文连贯性"""

    messages = [{"role": "system", "content": system}]
    if history:
        for item in history:
            try:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    user_msg = item[0] if item[0] else ""
                    bot_msg = item[1] if item[1] else ""
                    if user_msg and user_msg.strip():
                        messages.append({"role": "user", "content": user_msg})
                    if bot_msg and bot_msg.strip():
                        messages.append({"role": "assistant", "content": bot_msg})
                elif isinstance(item, dict):
                    role = item.get("role", "")
                    content = item.get("content", "")
                    if content and content.strip():
                        messages.append({"role": role, "content": content})
            except Exception as e:
                log_message(f"处理历史记录出错: {e}")
                continue
    messages.append({"role": "user", "content": prompt})
    data = {"model": MODEL_NAME, "messages": messages, "temperature": 0.1}

    try:
        log_message(f"请求AI，历史数: {len(history) if history else 0}")
        resp = requests.post(API_URL, headers=headers, json=data, timeout=150)
        cmds = resp.json()["choices"][0]["message"]["content"].strip()
        cleaned_cmds = cmds.replace("```bash", "").replace("```", "").strip()
        if "[非运维需求]" in cleaned_cmds or cleaned_cmds.lower() == "[非运维需求]":
            return "NON_OPERATION"
        log_message(f"AI返回: {cleaned_cmds[:50]}...")
        return cleaned_cmds
    except Exception as e:
        log_message(f"API异常: {str(e)}")
        return f"API_ERROR: {str(e)}"

def translate_to_human(user_prompt, raw_output):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    system = "你是贴心AI助理，把Linux输出翻译成口语化汇报，加Emoji，提炼核心。"
    prompt = f"用户需求：{user_prompt}\n终端输出：{raw_output}\n请自然语言汇报："
    data = {"model": MODEL_NAME, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "temperature": 0.5}
    try:
        resp = requests.post(API_URL, headers=headers, json=data, timeout=150)
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log_message(f"翻译API异常: {str(e)}")
        return raw_output

def bot(message, history):
    global pending_cmd_state
    log_message(f"用户输入: '{message}', 待确认命令: {pending_cmd_state}")
    confirm_keywords = ["确认执行", "yes", "是", "确定", "确认"]
    is_confirm = message.strip() in confirm_keywords or message.lower().strip() == "yes"

    if is_confirm and pending_cmd_state:
        log_message(f"✅ 执行确认的命令(跳过安全检查): {pending_cmd_state}")
        exec_result = safe_run(pending_cmd_state)
        human_report = translate_to_human(message, exec_result)
        result = f"### Minerva 汇报：\n{human_report}\n\n---\n<details><summary>查看底层执行</summary>\n```text\n【执行】{pending_cmd_state}\n【结果】{exec_result}\n```</details>"
        pending_cmd_state = None
        return result

    cmd_to_run = ask_ai_to_plan(message, history or [])
    if cmd_to_run == "NON_OPERATION":
        return "🤔 抱歉，我无法识别这个需求。我是 Linux 运维助手，请提供具体的运维指令（如：查看磁盘、创建用户、查看进程等）"
    if cmd_to_run.startswith("API_ERROR"):
        return f"⚠️ 大脑连接失败：{cmd_to_run}\n\n请检查 API 配置或稍后重试。"

    commands = cmd_to_run.split('\n')
    execution_logs = []
    for cmd in commands:
        cmd = cmd.strip()
        if not cmd: continue
        passed, level, msg = check_security(cmd)
        if level == "BLOCK":
            log_message(f"高危命令被拦截: {cmd}")
            return msg + "\n\n💡 你可以继续输入其他指令。"
        elif level == "CONFIRM":
            log_message(f"⚠️ 需要确认的命令: {cmd}")
            pending_cmd_state = cmd
            return msg
        exec_result = safe_run(cmd)
        execution_logs.append(f"【执行】{cmd}\n【结果】{exec_result}")

    full_raw_output = "\n\n".join(execution_logs)
    human_report = translate_to_human(message, full_raw_output)
    result = f"### Minerva 汇报：\n{human_report}\n\n---\n<details><summary>查看底层执行</summary>\n```text\n{full_raw_output}\n```</details>"
    return result

# ==================== UI 美化部分 ====================

# ==================== UI 美化部分 ====================

# ... 前面所有后端逻辑 (check_security, safe_run, bot 等) 保持完全不变 ...

# ==================== UI 美化部分 ====================

if __name__ == "__main__":
    custom_css = """
    footer {visibility: hidden}
    .main-container {
        max-width: 1000px !important;
        margin: 0 auto !important;
        padding-top: 2rem !important;
    }
    #chatbot-header {
        text-align: center;
        margin-bottom: 20px;
    }
    #chatbot-header h1 {
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #2D3FE2, #00C6FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    .gradio-container .message-wrap .message {
        border-radius: 12px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    """
    theme = gr.themes.Soft(primary_hue="blue", spacing_size="sm", radius_size="md")

    # 1. 这里移除了 theme 和 css 参数
    with gr.Blocks(theme=theme, css=custom_css) as demo:
        with gr.Column(elem_classes="main-container"):
            
            # 2. 将 gr.Div 替换为 gr.Group 或直接使用 Markdown 组合
            with gr.Group(elem_id="chatbot-header"):
                gr.Markdown("# 🤖 AI Linux 助手")
                gr.Markdown("### Minerva 运维专家：对话即操作，安全且高效")
            
            chat = gr.ChatInterface(
                fn=bot,
                chatbot=gr.Chatbot(
                    height=600, 
                    # 删掉 bubble_full_width=False
                    show_label=False,
                    avatar_images=(None, "https://api.dicebear.com/7.x/bottts/svg?seed=Minerva")
                ),
                textbox=gr.Textbox(
                    placeholder="请输入运维需求（例如：帮我看看系统负载...）",
                    container=False,
                    scale=7
                ),
                submit_btn="发送指令",
                stop_btn="停止生成",
                # retry_btn="重新生成",
                # undo_btn="撤销",
                # clear_btn="清空对话",
            )
            
            gr.Markdown(
                "💡 **温馨提示**：本助手具备安全审计功能，高危指令将被拦截，变更操作需人工确认。",
                elem_id="footer-note"
            )

    log_message("系统启动完成")
    
    # 3. 将 theme 和 css 挪到这里
    demo.launch(
        server_name="0.0.0.0", 
        server_port=7860
    )
