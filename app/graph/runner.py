"""
[역할] 그래프 호출 공통 헬퍼. CLI(app/main.py)와 Streamlit(app/streamlit_app.py) 양쪽에서
"사용자 입력 한 턴을 그래프에 흘려보내고 결과를 받는" 로직을 중복 작성하지 않도록 모았습니다.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from app.graph.builder import build_graph


def run_turn(user_text: str, session_id: str) -> dict:
    """사용자 발화 1건을 그래프에 넣고 최종 State(dict)를 반환한다.

    `config={"configurable": {"thread_id": session_id}}` 가 LangGraph checkpointer에게
    "이 session_id의 이전 대화 State를 이어서 쓰라"고 알려주는 지점입니다. 이 값이
    바뀌면 완전히 새로운 대화로 취급됩니다 (멀티턴 메모리는 thread_id 단위로 격리됨).
    """
    graph = build_graph()
    config = {"configurable": {"thread_id": session_id}}
    result = graph.invoke(
        {"messages": [HumanMessage(content=user_text)], "session_id": session_id},
        config=config,
    )
    return result


def get_history(session_id: str) -> list:
    """저장된 세션의 대화 이력(messages)만 조회한다. 그래프를 새로 실행하지 않는다."""
    graph = build_graph()
    config = {"configurable": {"thread_id": session_id}}
    snapshot = graph.get_state(config)
    return snapshot.values.get("messages", []) if snapshot else []
