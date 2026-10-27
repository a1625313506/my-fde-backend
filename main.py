from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import os
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# ================= 1. 基础配置与数据库 =================
load_dotenv()
API_KEY = os.getenv("ZHIPU_API_KEY")

# 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./chat.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 定义数据表
class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String)
    content = Column(Text)

# 建表
Base.metadata.create_all(bind=engine)

app = FastAPI()

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= 2. 定义数据格式 =================
class ChatRequest(BaseModel):
    messages: list

# ================= 3. 核心业务逻辑 =================
@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    history_messages = request.messages
    
    # 提取最后一条用户消息存入数据库
    user_msg = history_messages[-1]["content"]
    db = SessionLocal()
    try:
        new_msg = MessageModel(role="user", content=user_msg)
        db.add(new_msg)
        db.commit()
    finally:
        db.close()

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 转换角色格式
    ai_messages = [{"role": "system", "content": "你是一个专业的AI助手。"}]
    for msg in history_messages:
        if not msg["content"].strip():
            continue
        if msg["role"] == "user":
            ai_messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "ai":
            ai_messages.append({"role": "assistant", "content": msg["content"]})

    data = {
        "model": "glm-4-flash",
        "messages": ai_messages,
        "stream": True
    }

    # 流式生成器
    async def generate():
        full_ai_reply = "" 
        
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=data, timeout=30.0) as response:
                async for chunk in response.aiter_lines():
                    if chunk:
                        yield chunk + "\n"
                        
                        # 收集完整回复
                        if chunk.startswith("data: "):
                            data_str = chunk.replace("data: ", "").strip()
                            if data_str and data_str != "[DONE]":
                                try:
                                    parsed = json.loads(data_str)
                                    text_chunk = parsed["choices"][0]["delta"].get("content", "")
                                    full_ai_reply += text_chunk
                                except Exception:
                                    pass
                                    
        # 存入数据库（注意：这里的缩进必须在 async with 外面，与 async for 平齐）
        if full_ai_reply:
            db = SessionLocal()
            try:
                ai_msg = MessageModel(role="ai", content=full_ai_reply)
                db.add(ai_msg)
                db.commit()
            finally:
                db.close()

    return StreamingResponse(generate(), media_type="text/event-stream")

# ================= 4. 获取历史记录 =================
@app.get("/history")
async def get_history():
    db = SessionLocal()
    try:
        messages = db.query(MessageModel).order_by(MessageModel.id).all()
        result = [{"id": m.id, "role": m.role, "content": m.content} for m in messages]
        return {"history": result}
    finally:
        db.close()