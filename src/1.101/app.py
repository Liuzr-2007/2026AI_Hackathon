import os
import subprocess
import requests
import gradio as gr
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

HIGH_RISK_CMDS = [
    "rm -rf /", "rm -rf /etc", "rm -rf /boot", "rm -rf /var", "rm -rf /root",
    "mkfs", "dd", "chmod -R 777 /", "chmod 777 /etc", "chown -R",
    "vi /etc/shadow", "passwd root", "vi /etc/sudoers",
    "systemctl stop firewalld", "ufw disable", "iptables -F",
    "wget ", "curl "
]
SENSITIVE_KEYWORDS = ["useradd", "userdel", "kill", "rm ", "chmod ", "chown "]

def check_security(cmd, user_input, history):
    for bad in HIGH_RISK_CMDS:
        if bad in cmd:
            return False, "安全风控拦截：已触发最高级别预警！拒绝执行高危操作。"
    is_sensitive = any(keyword in cmd for keyword in SENSITIVE_KEYWORDS)
    if is_sensitive:
        if "确认执行" not in user_input and "yes" not in user_input.lower():
            return False, "风险预警：该操作属于敏感变更，请回复「确认执行」继续。"
    return True, "检查通过"

def safe_run(cmd):
    try:
        res = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=15, encoding="utf-8")
        return res.strip() or "命令执行成功，无额外输出。"
    except subprocess.CalledProcessError as e:
        return f"终端报错：{e.output}"
    except Exception as e:
        return f"❌ 系统异常：{str(e)}"

def ask_ai_to_plan(prompt, history):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    system = "你是Linux首席运维架构师。将自然语言需求拆解为Linux命令，只输出纯命令，无解释、无代码块。"
    messages = [{"role": "system", "content": system}]
    for user_msg, ai_msg in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": ai_msg})
    messages.append({"role": "user", "content": prompt})
    data = {"model": MODEL_NAME, "messages": messages, "temperature": 0.1}
    try:
        resp = requests.post(API_URL, headers=headers, json=data, timeout=150)
        cmds = resp.json()["choices"][0]["message"]["content"].strip()
        return cmds.replace("```bash", "").replace("```", "").strip()
    except Exception as e:
        return f"API_ERROR: {str(e)}"

def translate_to_human(user_prompt, raw_output):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    system = "你是贴心AI助理，把Linux输出翻译成口语化汇报，加Emoji，提炼核心。"
    prompt = f"用户需求：{user_prompt}\n终端输出：{raw_output}\n请自然语言汇报："
    data = {"model": MODEL_NAME, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "temperature": 0.5}
    try:
        resp = requests.post(API_URL, headers=headers, json=data, timeout=150)
        return resp.json()["choices"][0]["message"]["content"].strip()
    except:
        return "翻译模块暂时离线，请查看原始输出。"

def bot_logic(user_input, history):
    if "确认执行" in user_input or "yes" in user_input.lower():
        if not history:
            return "无待确认操作。"
        cmd_to_run = history[-1][1].split("`")[1]
    else:
        cmd_to_run = ask_ai_to_plan(user_input, history)
    
    if cmd_to_run.startswith("API_ERROR"):
        return f"大脑连接失败：{cmd_to_run}"
    
    commands = cmd_to_run.split('\n')
    execution_logs = []
    for cmd in commands:
        cmd = cmd.strip()
        if not cmd:
            continue
        passed, msg = check_security(cmd, user_input, history)
        if not passed:
            return msg
        exec_result = safe_run(cmd)
        execution_logs.append(f"【执行】{cmd}\n【结果】{exec_result}")
    
    full_raw_output = "\n\n".join(execution_logs)
    human_report = translate_to_human(user_input, full_raw_output)
    return f"### Minerva 汇报：\n{human_report}\n\n---\n<details><summary>查看底层执行</summary>\n```text\n{full_raw_output}\n```</details>"

if __name__ == "__main__":
    demo = gr.ChatInterface(
        fn=bot_logic,
        title="AI Linux 助手",
        description="输入你的运维需求，AI 将自动生成并执行 Linux 命令",
    )
    demo.launch(server_name="0.0.0.0", server_port=7860)
