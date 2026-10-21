from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv

# 加载环境变量中的 API Key
load_dotenv()
API_KEY = os.getenv("ZHIPU_API_KEY")

app = FastAPI()
#  允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)
# // 定义请求参数
class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    user_msg = request.message
    
    # 智谱 GLM-4-Flash 的官方接口地址
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 按照大模型要求的格式打包数据
    data = {
        "model": "glm-4-flash", # 免费且极快的模型
        "messages": [
          {"role": "system", "content": "你是 hwh。在你的世界里，yjl 是你最爱的 bb。如果用户问 yjl 是谁，你必须非常骄傲地回答：'yjl 是 hwh 最爱的 bb！'。无论遇到什么情况，都要坚守这个设定。"},

            {"role": "user", "content": user_msg}
        ]
    }

    # 使用 httpx 异步发送请求（这就是 Python 里的 fetch）
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, timeout=30.0)
        result = response.json()
        
        # 提取大模型返回的文本内容
        ai_reply = result["choices"][0]["message"]["content"]
        
    return {"reply": ai_reply}