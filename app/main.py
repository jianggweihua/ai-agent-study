from fastapi import FastAPI
from pydantic import BaseModel
from app.agent import run_agent

app = FastAPI()


# =====================
# 数据模型
# =====================

class Question(BaseModel):
    question: str



# =====================
# Tools
# =====================






# =====================
# Agent核心
# =====================




# =====================
# API接口
# =====================


@app.post("/agent")
async def agent(data: Question):
    answer = await run_agent(data.question)
    return {
    "answer": answer,
    "version": "v3"
}