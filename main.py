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
    messages: list

# 4. 接口定义
@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    # 1. 拿到前端传来的完整历史记录（已经包含刚发的那句）
    history_messages = request.messages
    
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 2. 把前端的格式（带id）转换成大模型要求的格式（只留role和content）
    ai_messages = [{"role": "system", "content": "你是一个专业的AI助手。"}]
    for msg in history_messages:
        if not msg["content"].strip():
            continue
        if msg["role"] == "user":
            ai_messages.append({
                "role": "user",
                "content": msg["content"]
            })
        elif msg["role"] == "ai":
            # 🌟 核心修改：把前端的 "ai" 翻译成大模型的 "assistant"
            ai_messages.append({
                "role": "assistant",
                "content": msg["content"]
            })
        # 警告气泡 (warn) 直接忽略
    data = {
        "model": "glm-4-flash",
        "messages": ai_messages, # 🌟 把整理好的历史记录传过去
        "stream": True
    }

    # 下面的 generate 生成器代码保持不变 ...
    async def generate():
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=data, timeout=30.0) as response:
                async for chunk in response.aiter_lines():
                    if chunk:
                        yield chunk + "\n"

    return StreamingResponse(generate(), media_type="text/event-stream")