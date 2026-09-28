from app.rag import rag_search


# 给 LLM 看的“工具说明书”
TOOLS = [
    {
        "name": "rag_search",
        "description": "查询公司的培训、请假、报销等内部资料",
    },
    {
        "name": "text_length",
        "description": "统计文本字符数量",
    },
]


# 真正的 Python 工具
def text_length(text: str) -> int:
    """统计文本字符数量。"""
    return len(text)


# 统一执行工具
def run_tool(name: str, argument: str):
    if not isinstance(argument, str):
        return "工具参数必须是字符串"

    if name == "rag_search":
        return rag_search(argument)

    if name == "text_length":
        return str(text_length(argument))

    return "没有找到这个工具"
