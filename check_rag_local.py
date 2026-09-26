"""检查当前学习项目的本地模拟知识检索，不调用模型或外部 API。"""

from app.rag import rag_search
from app.tools import text_length


if __name__ == "__main__":
    expected = "公司培训规定：公司每年提供一次免费的职业技能培训。"
    cases = ["公司有什么培训规定？", "培训每年有几次？"]
    for question in cases:
        context = rag_search(question)
        print(f"问题：{question}\n找到的资料：{context}\n")
        if context != expected:
            raise AssertionError(f"预期找到：{expected}")
    if text_length(expected) != 25:
        raise AssertionError("培训资料字符统计应为 25")
    print("当前模拟知识检索和字符统计检查通过；没有调用模型或外部 API。")
