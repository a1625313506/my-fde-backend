from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv

# 1. 加载环境变量中的 API Key
load_dotenv()
API_KEY = os.getenv("ZHIPU_API_KEY")

app = FastAPI()

# 2. 解决跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 定义接收的数据格式
class ChatRequest(BaseModel):
    message: str

# 4. 接口定义
@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    user_msg = request.message
    
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "system", "content": "你是 hwh。在你的世界里，yjl 是你最爱的 bb。"},
            {"role": "user", "content": user_msg}
        ],
        "stream": True  # 🌟 核心：告诉大模型，我要开启流式输出！
    }

    # 定义一个异步生成器，不断去接大模型吐出来的字
    async def generate():
        async with httpx.AsyncClient() as client:
            # 注意这里把 post 改成了 stream
            async with client.stream("POST", url, headers=headers, json=data, timeout=30.0) as response:
                # 按行读取大模型吐出的数据
                async for chunk in response.aiter_lines():
                    if chunk:
                        # 把大模型返回的原始格式直接转给前端
                        yield chunk + "\n"

    # 返回流式响应
    return StreamingResponse(generate(), media_type="text/event-stream")