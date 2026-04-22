import os
from dotenv import load_dotenv
import requests

# 加载本地配置文件
load_dotenv()

# 从环境变量读取API信息
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

def chat_with_glm(prompt):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    response = requests.post(API_URL, headers=headers, json=data)
    return response.json()["choices"][0]["message"]["content"]

if __name__ == "__main__":
    print("GLM-4.6已就绪，输入‘exit’退出对话")
    while True:
        user_input = input("你：")
        if user_input.lower()=="exit":
            print("对话结束")
            break
        reply = chat_with_glm(user_input)
        print(f"GLM-4.6 ：{reply}")
