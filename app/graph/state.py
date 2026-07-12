"""
[역할] LangGraph의 State(그래프 전체가 공유하는 데이터) 스키마 정의.

LangGraph는 "모든 노드가 하나의 State 객체를 입력받아, 변경할 부분만 딕셔너리로
반환하면 자동으로 병합해주는" 방식으로 동작합니다. 이 State가 곧 그래프의 '메모리'이자
'상태'입니다 (평가항목 "메모리/상태 관리"의 핵심 구현 지점).

TypedDict + Annotated 리듀서(reducer) 패턴을 사용합니다:
    messages: Annotated[list[BaseMessage], add_messages]
위처럼 필드에 리듀서 함수를 지정하면, 노드가 `{"messages": [new_msg]}`를 반환할 때
리스트를 통째로 덮어쓰는 게 아니라 `add_messages`가 "기존 리스트에 이어붙이기"를
자동으로 해줍니다. 이게 바로 멀티턴 대화 이력이 누적되는 원리입니다.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # --- 대화 이력 (멀티턴 메모리의 핵심) ---
    # add_messages 리듀서 덕분에 매 턴 새 메시지가 "누적"됩니다.
    # 또한 checkpointer(app/memory/checkpointer.py)가 thread_id별로 이 State 전체를
    # 저장해두기 때문에, 같은 세션으로 다시 들어오면 이전 대화가 이어집니다.
    messages: Annotated[list[BaseMessage], add_messages]

    # --- 세션 식별자 (checkpointer의 thread_id와 동일한 값을 씀) ---
    session_id: str

    # --- guardrail_input 미들웨어가 채우는 필드 ---
    blocked: bool  # True면 이후 노드를 타지 않고 바로 거절 응답으로 종료
    block_reason: str

    # --- router 노드가 채우는 필드 (조건부 분기의 기준값) ---
    intent: Literal["dashboard", "free_query", "bookmark"]

    # --- 대시보드 흐름에서 각 Tool 노드가 채우는 필드 ---
    macro_snapshot: dict
    sector_snapshot: dict
    news_snapshot: dict

    # --- 자유 질의 흐름에서 RAG 노드가 채우는 필드 ---
    rag_context: str

    # --- 북마크 흐름 입력값 (프론트에서 "이 내용을 저장해줘"로 넘겨주는 원문) ---
    bookmark_content: str

    # --- 그래프의 최종 산출물 (output_parser 노드가 채움, 구조화 출력 결과) ---
    final_output: dict

    # --- error_handler 미들웨어가 예외를 잡으면 채우는 필드 ---
    error: str
