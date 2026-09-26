from ollama import chat as ollama_chat
from app.tools import text_length
from app.rag import rag_search
from app.mcp_client import call_mcp_hello





async def run_agent(question: str):

    # 1. MCP 工具
    if "打招呼" in question:
        return await call_mcp_hello("小明")

    # 2. 企业知识查询
    if "公司" in question or "培训" in question:
        result = rag_search(question)

        # 如果用户还要求统计字符
        if "字符" in question or "长度" in question:
            length = text_length(result)
            return f"{result}\n字符数：{length}"

        return result

    # 3. 普通问题交给本地 Qwen
    response = ollama_chat(
        model="qwen3:1.7b",
        messages=[
            {
                "role": "user",
                "content": question,
            }
        ],
    )

    return response.message.content