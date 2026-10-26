# 🧠 My AI Assistant (Backend)

基于 Python + FastAPI 构建的 AI 代理服务。负责接收前端请求，安全调用智谱 GLM 模型，并将结果以流式（SSE）转发。

## 🚀 技术栈
- **框架**: FastAPI + Uvicorn
- **网络**: HTTPX (异步流式请求)
- **安全**: python-dotenv (环境变量隔离)

## ✨ 核心功能
- **大模型接入**：封装智谱 GLM-4-Flash API，支持 System Prompt 角色设定。
- **SSE 流式输出**：利用 Python 生成器与 `StreamingResponse`，实现实时数据流。
- **安全与跨域**：配置 CORS，并通过 `.env` 隐藏 API Key。

## 📦 本地运行
1. `pip install fastapi uvicorn httpx python-dotenv`
2. 创建 `.env` 文件并写入：`ZHIPU_API_KEY=你的密钥`
3. 启动：`uvicorn main:app --reload`

> 前端仓库：[点击访问](https://github.com/a1625313506/my-fde-app)
