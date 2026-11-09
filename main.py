from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import os
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text,ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from fastapi import UploadFile, File
from pypdf import PdfReader
import io
import chromadb

# ================= 1. 基础配置与数据库 =================
load_dotenv()
API_KEY = os.getenv("ZHIPU_API_KEY")

# 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./chat.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
class ConversationModel(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String,default="新对话")

# 定义数据表
class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String)
    content = Column(Text)
    conversation_id = Column(Integer, ForeignKey("conversations.id"),nullable=True)
# 建表
Base.metadata.create_all(bind=engine)

app = FastAPI(root_path="/api")
# 创建一个本地文件夹存向量数据
chroma_client = chromadb.PersistentClient(path="./chroma_db")
# 创建一个集合（类似数据库里的表）
collection = chroma_client.get_or_create_collection(name="pdf_knowledge")
async def get_embeddings(texts: list[str]):
    url = "https://open.bigmodel.cn/api/paas/v4/embeddings"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "embedding-2", # 智谱的向量模型
        "input": texts
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, timeout=30.0)
        result = response.json()
        # 返回一个包含所有向量的列表
        return [item["embedding"] for item in result["data"]]
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
    conversation_id: int

# ================= 3. 核心业务逻辑 =================
@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    history_messages = request.messages
    conv_id = request.conversation_id
    
    user_msg = history_messages[-1]["content"]
    
    # 1. 存用户消息（保持原样）
    db = SessionLocal()
    try:
        new_msg = MessageModel(role="user", content=user_msg, conversation_id=conv_id)
        db.add(new_msg)
        db.commit()
    finally:
        db.close()

    # ==========================================
    # 🌟 核心新增：去向量库偷看小抄！
    # ==========================================
    try:
        # 把用户的问题变成向量
        query_embedding = await get_embeddings([user_msg])
        # 去数据库里找最相似的 2 个文本块
        results = collection.query(query_embeddings=query_embedding, n_results=2)
        
        # 把搜出来的结果拼成一段长文本
        context_text = "\n".join(results["documents"][0]) if results["documents"][0] else "无相关参考资料"
    except Exception as e:
        context_text = "检索知识库失败。"
        print(f"检索报错：{e}")

    # ==========================================
    # 🌟 核心改造：拼装带小抄的 System Prompt
    # ==========================================
    # 这里我们给 AI 下达极其严格的指令
    system_prompt = f"""你是一个专业的企业内部知识库助手。
请严格根据我提供的【参考资料】来回答用户的问题。
如果参考资料中找不到答案，请直接回答“抱歉，内部知识库中没有相关记录”，绝对不允许自己编造答案！

【参考资料】：
{context_text}
"""

    ai_messages = [{"role": "system", "content": system_prompt}]
    
    # 把历史记录塞进去（注意：历史记录里只放用户的纯文字，不需要放历史的小抄，不然 Token 会爆炸）
    for msg in history_messages:
        if msg["role"] == "user":
            ai_messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "ai":
            ai_messages.append({"role": "assistant", "content": msg["content"]})

    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "glm-4-flash",
        "messages": ai_messages, # 这里的 messages 已经悄悄带上了小抄
        "stream": True
    }
    
    # 下面的 generate() 流式代码保持完全不变...=

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
                ai_msg = MessageModel(role="ai", content=full_ai_reply,conversation_id=conv_id)
                db.add(ai_msg)
                db.commit()
            finally:
                db.close()

    return StreamingResponse(generate(), media_type="text/event-stream")
@app.post("/conversation/new")
async def creat_conversation():
    db=SessionLocal()
    try:
        new_conv=ConversationModel(title="新对话")
        db.add(new_conv)
        db.commit()
        db.refresh(new_conv)
        return{"conversation_id":new_conv.id}
    finally:
        db.close()
# ================= 4. 获取历史记录 =================
@app.get("/history/{conversation_id}")
async def get_history(conversation_id: int):
    db = SessionLocal()
    try:
        messages = db.query(MessageModel).filter(MessageModel.conversation_id == conversation_id).order_by(MessageModel.id).all()
        result = [{"id": m.id, "role": m.role, "content": m.content} for m in messages]
        return {"history": result}
    finally:
        db.close()
@app.get("/search")
async def search_knowledge(query: str):
    # 1. 把用户的提问也变成向量
    query_embedding = await get_embeddings([query])
    
    # 2. 去向量数据库里找最相似的 2 个文本块
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=2
    )
    
    return {"matched_text": results["documents"][0]}
@app.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        # 1. 读取前端传来的文件内容
        content = await file.read()
        
        # 2. 用 PdfReader 读取这个 PDF
        pdf_reader = PdfReader(io.BytesIO(content))
        
        # 3. 提取所有页面的文字
        full_text = ""
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        # 4. 最核心的一步：文本切分（Chunking）
        # 大模型一次吃不下太多字，我们需要把长文切成 500 字一段。
        chunk_size = 500
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        # ... 你的切块代码 chunks = [...] ...

        # 🌟 新增：把这堆 chunks 发给大模型，变成向量！
        embeddings = await get_embeddings(chunks)

        # 🌟 新增：存入 ChromaDB
        # 我们需要给每一块起一个唯一的 ID
        ids = [f"{file.filename}_{i}" for i in range(len(chunks))]
        
        collection.add(
            documents=chunks,        # 原文
            embeddings=embeddings,   # 向量数字
            ids=ids                  # 唯一身份证
        )

        return {
            "message": "文件解析并存入向量库成功！",
            "filename": file.filename,
            "chunks_count": len(chunks)
        }
        
    except Exception as e:
        return {"error": str(e)}
