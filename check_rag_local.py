"""使用真实 SentenceTransformer 和 ChromaDB 检查检索，不调用 Qwen。"""

from app.embedding import get_embedding
from app.rag import NO_RESULT, _ensure_index
from app.tools import run_tool, text_length


if __name__ == "__main__":

    vector = get_embedding("员工培训政策")
    assert isinstance(vector, list) and len(vector) == 384
    assert all(isinstance(value, float) for value in vector)

    cases = [
        ("员工培训政策", "公司培训制度："),
        ("请假制度查询", "公司请假制度："),
        ("公司是否提供火星旅行补贴？", NO_RESULT),
        ("不存在的问题", NO_RESULT),
        ("休假制度", "公司请假制度："),
    ]

    for question, expected in cases:
        context = run_tool("rag_search", question)
        print(f"\n问题：{question}")
        print(f"找到的资料：\n{context}")
        assert expected in context, (question, expected, context)
        if expected != NO_RESULT:
            assert NO_RESULT not in context

    collection = _ensure_index()
    records = collection.get(include=["documents", "embeddings"])
    assert collection.count() == 3, "当前三段制度应只索引一次"
    assert all(len(vector) == 384 for vector in records["embeddings"])
    assert text_length("培训ABC") == 5
    assert run_tool("text_length", "培训ABC") == "5"

    print("\n真实向量检索、未知问题、持久化索引和字符统计测试通过")
