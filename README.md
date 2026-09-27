# AI Agent 企业知识助手

一个基于 **FastAPI + LLM + Tool Calling + RAG + MCP + Docker** 的 AI Agent 学习与实践项目。

项目目标是实现一个能够理解用户问题、判断是否需要调用工具，并结合企业知识进行回答的 AI Agent。

---

## 项目架构

```text
用户
 ↓
FastAPI
 ↓
Agent
 ↓
LLM
 ↓
Decision
 ├── RAG
 ├── Tool
 └── MCP
 ↓
Observation
 ↓
Agent继续判断
 ↓
返回答案