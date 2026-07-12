"""
[역할] 자유 질의(free_query) 흐름의 핵심 - Tool-calling ReAct 루프.

이 파일의 두 함수가 LangGraph의 "반복(loop)" 요구사항을 구현하는 지점입니다.

    call_agent_llm(state)   : LLM에게 도구 목록을 bind_tools()로 알려주고, LLM이
                              스스로 "이 도구를 이 인자로 호출하겠다"를 결정하게 한다.
    should_continue(state)  : LLM의 응답에 tool_calls가 담겨 있으면 "tools" 노드로
                              보내고(도구 실행 후 다시 call_agent_llm으로 되돌아옴),
                              없으면 "output_parser"로 보내 루프를 종료한다.

그래프 상에서는:
    call_agent_llm --(tool_calls 있음)--> tools(ToolNode) --> call_agent_llm  (반복)
    call_agent_llm --(tool_calls 없음)--> output_parser --> END
이 구조가 바로 "Agent가 자율적으로 도구를 선택·실행"하는 요구사항의 구현입니다.
ToolNode 자체는 LangGraph가 제공하는 prebuilt 컴포넌트로, app/graph/builder.py에서
`ToolNode(ALL_TOOLS)`로 생성해 그래프에 등록합니다.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage

from app.llm import with_fallback
from app.tools import ALL_TOOLS

_SYSTEM_PROMPT_TEMPLATE = """너는 주식/매크로 정보를 제공하는 트레이딩 어시스턴트다.
사용자 질문에 답하기 위해 필요하면 제공된 도구(get_macro_indicators, get_sector_performance,
search_market_news, get_stock_quote)를 자유롭게 호출해라. 이미 충분한 정보가 있으면
도구를 더 호출하지 말고 바로 한국어로 답하라. 투자 자문이 아닌 정보 제공 목적임을 인지하고,
확정적인 투자 권유 표현("사세요/파세요")은 피하고 참고 정보로서 답하라.

아래는 RAG로 검색된 관련 참고 자료다 (없으면 무시해도 된다):
---
{rag_context}
---
"""


def call_agent_llm(state: dict) -> dict:
    rag_context = state.get("rag_context", "(검색된 참고 자료 없음)")
    system_message = SystemMessage(content=_SYSTEM_PROMPT_TEMPLATE.format(rag_context=rag_context))

    llm_with_tools = with_fallback(lambda m: m.bind_tools(ALL_TOOLS))
    response: AIMessage = llm_with_tools.invoke([system_message, *state.get("messages", [])])
    return {"messages": [response]}


def should_continue(state: dict) -> str:
    """conditional edge 판별 함수. 반환 문자열이 builder.py의 분기 매핑 키와 대응된다."""
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "tools"
    return "output_parser"
