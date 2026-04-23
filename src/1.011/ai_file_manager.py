import os
import subprocess
from dotenv import load_dotenv
import requests

load_dotenv()
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

BAN_CMDS = ["rm -rf /", "rm /*", "mkfs", "dd", "shutdown", "reboot", "chmod 777", "> /dev/sda"]

def safe_run(cmd):
    for bad in BAN_CMDS:
        if bad in cmd:
            return "❌ 危险命令，已拦截"
    try:
        res = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=15, encoding="utf-8")
        return res.strip() or "执行成功"
    except Exception as e:
        return f"执行失败：{str(e)}"

def ask_ai(prompt):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    system = """
你是Linux文件操作AI，只输出最终可执行的Linux命令，不要解释，不要多余内容，不要换行。
支持：mv、cp、ls、mkdir、rm（仅允许删除普通文件）、cat、pwd、find。
禁止输出任何危险命令。
用户说自然语言，你只输出命令。
"""
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }
    
    resp = requests.post(API_URL, headers=headers, json=data, timeout=150)
    return resp.json()["choices"][0]["message"]["content"].strip()

if __name__ == "__main__":
    print("AI 文件操控助手已启动")
    print("支持：移动、复制、新建、查看、删除、查找文件\n")
    while True:
        ipt = input("你：")
        if ipt in ["exit", "quit", "q"]:
            print("退出")
            break
        cmd = ask_ai(ipt)
        print(f"AI 执行：{cmd}")
        out = safe_run(cmd)
        print(f"结果：{out}\n")
