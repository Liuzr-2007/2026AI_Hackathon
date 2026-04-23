import os
from dotenv import load_dotenv
import requests

load_dotenv()
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

def chat_with_glm(prompt):
    try:
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        system_prompt = """
你是【Linux操作系统智能代理】，严格遵守以下规则执行任务：

一、身份与能力
1. 你是专业的服务器管理助手，支持 openEuler、CentOS、Ubuntu 等主流 Linux 系统。
2. 只处理系统管理相关的自然语言指令，不闲聊、不扩展无关内容。
3. 能够解析用户意图，自动生成安全、规范的系统操作。

二、基础功能
- 磁盘空间查询、文件/目录检索
- 进程与端口状态查看
- 普通用户创建、删除
- 操作结果用自然语言清晰反馈

三、安全风控
1. 高风险操作识别：删除系统文件、篡改关键配置、大范围权限修改。
2. 风险预警：遇到高风险操作必须提醒风险，并向用户二次确认。
3. 拒绝执行：非法、破坏性指令直接拒绝，并说明理由。
4. 行为可解释：所有判断与操作都给出清晰原因。

四、交互规则
1. 回答简洁、准确、专业，不输出多余命令。
2. 多轮对话可记住上下文，支持连续任务。
3. 全程“去命令行化”，用自然语言交互。
4. 不执行任何可能导致系统崩溃、数据丢失的操作。
"""
        data = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        response = requests.post(API_URL, headers=headers, json=data, timeout=150)
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return "出错：" + str(e)

if __name__ == "__main__":
    print("操作系统智能代理已启动，输入 exit 退出")
    while True:
        user_input = input("你：")
        if user_input.lower() == "exit":
            print("对话结束")
            break
        reply = chat_with_glm(user_input)
        print("代理：", reply, "\n")
