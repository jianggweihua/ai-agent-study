import json
from typing import Any

from ollama import chat as ollama_chat

from app.mcp_client import call_mcp_hello
from app.tools import TOOLS, run_tool


def _extract_decision(content: str) -> dict[str, Any] | None:
    """从纯文本或 Markdown 代码块中提取第一个有效 Agent JSON 对象。"""
    decoder = json.JSONDecoder()

    for start, character in enumerate(content):
        if character != "{":
            continue

        try:
            decision, _ = decoder.raw_decode(content[start:])
        except json.JSONDecodeError:
            continue

        if isinstance(decision, dict) and decision.get("action") in {"tool", "answer"}:
            return decision

    return None


def _asks_for_char_count(question: str) -> bool:
    markers = ("字符数量", "字符数", "统计字符", "字符个数", "字数")
    return any(marker in question for marker in markers)


async def run_agent(question: str):
    # 保留项目现有的 MCP 打招呼入口。
    if "打招呼" in question:
        return await call_mcp_hello("小明")

    system_prompt = f"""
你是一个 AI Agent。你必须根据用户问题和可用工具决定下一步。

可用工具：
{json.dumps(TOOLS, ensure_ascii=False)}

强制规则：
1. 用户询问公司、培训、请假、报销或任何内部制度时，必须先调用 rag_search。严禁直接回答、猜测或仅凭常识作答。argument 必须是用户的原始问题。
2. 用户要求统计文本字符数量时，调用 text_length。
3. 调用工具时，只能输出一个有效 JSON 对象，不得添加 Markdown 代码围栏、说明文字或其他内容，格式如下：
   {{"action":"tool","tool":"rag_search","argument":"用户问题"}}
4. Python 执行工具后会把 Observation 发回给你。你必须依据原始问题和 Observation 再作答；不要在收到工具结果前给出最终答案。查询整体制度时，完整列出资料中的要点，保留“原则上”“超过三天”等限定条件。
5. 工具结果不足或没有相关资料时，必须说明“知识库中未找到相关资料，无法确认”。信息缺失不代表公司不提供、不允许或不存在该政策，禁止据此作否定断言。
6. 只有任务完成后才输出最终答案 JSON：
   {{"action":"answer","answer":"最终答案"}}
7. 每次回复都必须是一个有效 JSON 对象，且只能使用上述 action 格式。
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    # 限制 Agent 循环次数，避免模型重复调用工具。
    for _ in range(4):
        response = ollama_chat(
            model="qwen3:1.7b",
            messages=messages,
        )

        content = (response.message.content or "").strip()
        print(content)
        decision = _extract_decision(content)

        if decision is None:
            messages.extend(
                [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "上次回复无法解析为有效 JSON。请严格遵守 system 规则，"
                            "只输出一个完整、有效的 tool 或 answer JSON 对象，不要输出 Markdown。"
                        ),
                    },
                ]
            )
            continue

        if decision["action"] == "answer":
            answer = decision.get("answer", "")
            return answer if isinstance(answer, str) else str(answer)

        tool_name = decision.get("tool")
        argument = decision.get("argument", "")
        if not isinstance(tool_name, str) or not isinstance(argument, str):
            messages.extend(
                [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": "工具名称和 argument 必须是字符串，请重新输出有效 JSON。",
                    },
                ]
            )
            continue

        # Python 执行工具，随后把 Observation 交回 Qwen。
        print(f"[tool_call] {tool_name}")
        observation = run_tool(tool_name, argument)

        # Return retrieved policy text verbatim so Qwen cannot omit policy clauses.
        # When the user also asks for a count, count that exact retrieved text.
        if tool_name == "rag_search":
            if observation == "没有找到相关资料":
                return "知识库中未找到相关资料，无法确认"
            if _asks_for_char_count(question):
                print("[tool_call] text_length")
                char_count = run_tool("text_length", observation)
                return f"{observation}\n\n字符数量：{char_count}"
            return observation

        observation_text = (
            observation
            if isinstance(observation, str)
            else json.dumps(observation, ensure_ascii=False)
        )
        messages.extend(
            [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        f"工具 {tool_name} 已执行。\n\n"
                        f"Observation：\n{observation_text}\n\n"
                        "请根据原始问题和 Observation 给出最终答案。"
                        "如果没有相关资料，答案必须明确写出“知识库中未找到相关资料，无法确认”，"
                        "不能推断公司没有或不提供相应制度、福利或补贴。并严格只输出："
                        "{\"action\":\"answer\",\"answer\":\"最终答案\"}"
                    ),
                },
            ]
        )

    return "Agent 已达到最大执行步骤，未能生成有效的最终答案。"
