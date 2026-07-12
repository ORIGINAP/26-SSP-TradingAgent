"""
[역할] bookmark 노드 - 사용자가 저장을 요청한 정보를 RAG 벡터스토어에 즉시 적재한다.

이 노드가 실행되면 "지금 이 순간의 정보"가 장기 기억(벡터스토어)으로 옮겨지고,
이후 free_query 흐름의 rag_node.retrieve_and_augment가 이 내용을 검색해서
답변에 활용할 수 있게 된다. README에서 말한 "북마크된 정보가 RAG화되어 더 나은
답변에 사용된다"의 실제 구현 지점.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from app.rag.ingest import ingest_bookmark

# 저장 확인 메시지(🔖)나 가드레일 차단 메시지(⚠️) 자체는 "정보"가 아니므로, 직전
# AI 메시지로 폴백할 때 이런 메시지는 건너뛴다. 이 가드가 없으면 router가 실수로
# 연속된 메시지를 전부 bookmark로 분류했을 때, 매번 직전 확인 메시지를 다시
# 북마크하는 무의미한 루프가 생긴다 (실제로 겪은 버그).
_SKIP_PREFIXES = ("🔖", "⚠️")


def save_bookmark_node(state: dict) -> dict:
    session_id = state.get("session_id", "unknown")
    content = state.get("bookmark_content")

    if not content:
        # 명시적 북마크 내용이 없으면, 바로 직전 "실제 정보를 담은" AI 답변을 대상으로 삼는다.
        messages = state.get("messages", [])
        ai_messages = [
            m for m in messages
            if isinstance(m, AIMessage) and str(m.content).strip() and not str(m.content).startswith(_SKIP_PREFIXES)
        ]
        content = str(ai_messages[-1].content) if ai_messages else ""

    if not content:
        return {"messages": [AIMessage(content="저장할 내용을 찾지 못했습니다. 먼저 질문을 해서 답변을 받은 뒤 북마크해주세요.")]}

    ingest_bookmark(content, session_id=session_id)
    return {"messages": [AIMessage(content="🔖 북마크에 저장했습니다. 앞으로 관련 질문에 이 내용을 참고할게요.")]}
