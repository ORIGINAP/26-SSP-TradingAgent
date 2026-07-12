"""
[역할] output_parser 노드 - 그래프의 마지막 노드. intent별로 흩어져 있던 state를
하나의 구조화된 final_output(dict)으로 정리해서, 프론트엔드가 일관된 형태로
소비할 수 있게 만든다.

free_query 흐름에서는 여기서 다시 한 번 `with_structured_output(AgentAnswer)`를
사용해, LLM이 자유롭게 쓴 마지막 답변을 "answer / sources / used_tools" 필드로
구조화한다. (요구사항의 "OutputParser 최소 1개 지점" 조건은 router.py에서도
이미 충족하지만, 최종 사용자 응답 지점에도 적용해 일관성을 높였다.)
"""

from __future__ import annotations

import re

from langchain_core.messages import AIMessage, ToolMessage

from app.llm import with_fallback
from app.schemas.models import AgentAnswer

# ToolMessage.content는 Tool의 반환값을 str()으로 직렬화한 것이라, dict 안의 URL이
# "'https://...'," 처럼 따옴표/쉼표에 둘러싸여 나온다. 단순 split+startswith("http")는
# 이 따옴표 때문에 실패하므로, URL 형태를 직접 정규식으로 뽑아낸다.
_URL_PATTERN = re.compile(r"https?://[^\s'\"\)\],]+")


def format_output_node(state: dict) -> dict:
    intent = state.get("intent")

    if intent == "dashboard":
        return {
            "final_output": {
                "type": "dashboard",
                "macro": state.get("macro_snapshot"),
                "sector": state.get("sector_snapshot"),
                "news": state.get("news_snapshot"),
            }
        }

    if intent == "bookmark":
        messages = state.get("messages", [])
        last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
        return {"final_output": {"type": "bookmark", "message": last_ai.content if last_ai else ""}}

    # intent == "free_query"
    return {"final_output": {"type": "answer", **_build_agent_answer(state).model_dump()}}


def _build_agent_answer(state: dict) -> AgentAnswer:
    messages = state.get("messages", [])

    # 이번 턴에 호출된 ToolMessage들을 모아 used_tools/sources를 뽑아낸다.
    # (마지막 HumanMessage 이후에 쌓인 메시지만 "이번 턴"으로 간주)
    turn_messages: list = []
    for message in reversed(messages):
        turn_messages.append(message)
        if message.type == "human":
            break
    turn_messages.reverse()

    used_tools = sorted({m.name for m in turn_messages if isinstance(m, ToolMessage) and m.name})
    sources: list[str] = []
    for m in turn_messages:
        if isinstance(m, ToolMessage):
            sources.extend(_URL_PATTERN.findall(str(m.content)))
    sources = sorted(set(sources))

    last_ai = next((m for m in reversed(turn_messages) if isinstance(m, AIMessage)), None)
    draft_answer = str(last_ai.content) if last_ai else "답변을 생성하지 못했습니다."

    llm = with_fallback(lambda m: m.with_structured_output(AgentAnswer))
    structured: AgentAnswer = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "아래 초안 답변을 다듬어 최종 answer로 만들고, 주어진 sources/used_tools "
                    "목록을 그대로 채워라 (새로 만들어내지 마라)."
                ),
            },
            {
                "role": "user",
                "content": f"초안: {draft_answer}\nsources: {sources}\nused_tools: {used_tools}",
            },
        ]
    )
    return structured
