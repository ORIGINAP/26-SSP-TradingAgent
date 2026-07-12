"""
[역할] 이 프로젝트의 심장부 - 모든 노드/미들웨어/도구를 하나의 LangGraph StateGraph로
조립하는 곳. 요구사항 "LangGraph로 전체 실행 흐름(StateGraph)을 설계"의 구현체입니다.

[전체 그래프 구조]

    START
      -> guardrail_input                      (Middleware: 입력검증/속도제한)
      -> route_gate  --(blocked)-->            END  (차단 시 바로 종료)
                     --(ok)-->     router
      -> router  --(conditional edge #1)--> intent 로 3분기
           - "dashboard"  -> macro -> sector -> news -> output_parser -> END
           - "bookmark"   -> bookmark -> output_parser -> END
           - "free_query" -> rag_retrieve -> agent_llm
                                agent_llm --(conditional edge #2, 반복 루프)-->
                                    tool_calls 있음: tools(ToolNode) -> agent_llm (되돌아감)
                                    tool_calls 없음: output_parser -> END

조건부 분기가 2곳(route_gate, agent_llm 이후), 반복 루프가 1곳(agent_llm <-> tools)
있어 요구사항 "최소 1개 이상의 조건부 분기"와 "반복(loop)"을 모두 충족합니다.

[미들웨어 적용 방식] log_node/safe_node 데코레이터를 모든 노드 등록 시 일괄
적용합니다 (add_node 호출부의 _wrap 헬퍼 참고). 이렇게 하면 노드 함수 본문은
비즈니스 로직에만 집중하고, 로깅/예외처리는 여기 한 곳에서 보장됩니다.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.graph.middleware.error_handler import safe_node
from app.graph.middleware.guardrail import guardrail_input
from app.graph.middleware.logging_mw import log_node
from app.graph.nodes.agent import call_agent_llm, should_continue
from app.graph.nodes.bookmark import save_bookmark_node
from app.graph.nodes.macro import run_macro_node
from app.graph.nodes.news import run_news_node
from app.graph.nodes.output import format_output_node
from app.graph.nodes.rag_node import retrieve_and_augment
from app.graph.nodes.router import route_intent
from app.graph.nodes.sector import run_sector_node
from app.graph.state import AgentState
from app.memory.checkpointer import get_checkpointer
from app.tools import ALL_TOOLS


def _wrapped(name: str, fn):
    """로깅 + 예외처리 미들웨어를 노드 함수에 씌운다.

    적용 순서가 중요합니다: safe_node가 가장 바깥쪽이라, log_node가 예외를
    감지해 로그를 남긴 뒤 다시 던진(raise) 예외를 safe_node가 최종적으로 흡수합니다.
    """
    return safe_node(name)(log_node(name)(fn))


def _route_after_guardrail(state: dict) -> str:
    """조건부 분기 #1 - 가드레일에서 막혔으면 바로 종료, 아니면 라우터로."""
    return "blocked" if state.get("blocked") else "ok"


def _route_after_router(state: dict) -> str:
    """조건부 분기 #2 - router가 분류한 intent 값 그대로 다음 노드 이름을 결정."""
    return state.get("intent", "free_query")


@lru_cache(maxsize=1)
def build_graph():
    """StateGraph를 조립하고 컴파일해서 반환한다 (프로세스당 1회만 빌드, 이후 재사용)."""
    graph = StateGraph(AgentState)

    # --- 노드 등록: 모든 노드가 로깅+예외처리 미들웨어로 감싸져 있음 ---
    graph.add_node("guardrail", _wrapped("guardrail", guardrail_input))
    graph.add_node("router", _wrapped("router", route_intent))
    graph.add_node("macro", _wrapped("macro", run_macro_node))
    graph.add_node("sector", _wrapped("sector", run_sector_node))
    graph.add_node("news", _wrapped("news", run_news_node))
    graph.add_node("bookmark", _wrapped("bookmark", save_bookmark_node))
    graph.add_node("rag_retrieve", _wrapped("rag_retrieve", retrieve_and_augment))
    graph.add_node("agent_llm", _wrapped("agent_llm", call_agent_llm))
    graph.add_node("tools", ToolNode(ALL_TOOLS))  # LangGraph prebuilt 노드 (도구 실행 전담)
    graph.add_node("output_parser", _wrapped("output_parser", format_output_node))

    # --- 엣지 연결 ---
    graph.add_edge(START, "guardrail")

    graph.add_conditional_edges(
        "guardrail",
        _route_after_guardrail,
        {"blocked": END, "ok": "router"},
    )

    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "dashboard": "macro",
            "bookmark": "bookmark",
            "free_query": "rag_retrieve",
        },
    )

    # dashboard 흐름: 3개 Tool 노드를 순차 실행 후 출력 정리
    graph.add_edge("macro", "sector")
    graph.add_edge("sector", "news")
    graph.add_edge("news", "output_parser")

    # bookmark 흐름
    graph.add_edge("bookmark", "output_parser")

    # free_query 흐름: RAG 검색 -> ReAct 루프(Agent가 도구 자율 호출) -> 출력 정리
    graph.add_edge("rag_retrieve", "agent_llm")
    graph.add_conditional_edges(
        "agent_llm",
        should_continue,
        {"tools": "tools", "output_parser": "output_parser"},
    )
    graph.add_edge("tools", "agent_llm")  # 도구 실행 후 다시 LLM에게 돌아가는 반복(loop)

    graph.add_edge("output_parser", END)

    # checkpointer를 연결해 컴파일 -> thread_id 기준 세션 상태가 자동으로 저장/복원됨
    return graph.compile(checkpointer=get_checkpointer())


def export_mermaid() -> str:
    """워크플로우 다이어그램(mermaid)을 문자열로 반환. scripts/export_graph_diagram.py 에서 사용."""
    return build_graph().get_graph().draw_mermaid()
