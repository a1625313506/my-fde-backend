from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# 1. 解决跨域问题（重点！）
# 浏览器默认禁止前端(localhost:5173)访问后端(localhost:8000)，这段代码是给后端开门。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有前端地址访问
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 定义接收的数据格式（类似 Java 里的 DTO / 实体类）
class ChatRequest(BaseModel):
    message: str

# 3. 写一个 POST 接口，路径叫 /chat
@app.post("/chat")
async def chat_with_ai(request: ChatRequest):
    user_msg = request.message
    
    # 这里就是以后接大模型的地方，今天我们先手动模拟
    ai_reply = f"【后端 Python 收到】你刚才说的是：'{user_msg}'。前端和后端已经成功打通！"
    
    return {"reply": ai_reply}