"""
[역할] LangGraph의 "단기 기억(세션/대화 상태)"을 담당하는 Checkpointer 팩토리.

[개념] LangGraph의 checkpointer는 `graph.invoke(..., config={"configurable": {"thread_id": X}})`
호출마다 State 전체 스냅샷을 thread_id 기준으로 저장/복원해줍니다. 같은 thread_id로
다시 요청하면 이전 대화(state["messages"])가 자동으로 이어집니다 - 이것이 이 프로젝트의
"멀티턴 대화" 요구사항의 실제 구현체입니다. (RAG/북마크가 담당하는 '장기 기억'과는
구분되는 '단기 세션 기억' 계층입니다.)

SqliteSaver를 사용해 파일(data/checkpoints.sqlite)에 영속화합니다. 이러면 프로세스를
재시작해도(streamlit 서버 재기동 등) 세션이 끊기지 않습니다. 인메모리(MemorySaver)보다
데모 안정성이 높아서 선택했습니다.

[구현 노트] `SqliteSaver.from_conn_string(...)`는 문서상 with-블록으로만 쓰도록
안내되지만, 이 앱은 Streamlit처럼 프로세스가 계속 떠있는 장수명(long-lived)
서버라 요청마다 커넥션을 열고 닫기보다 커넥션 하나를 앱 생명주기 동안 재사용하는
편이 낫습니다. 그래서 sqlite3.Connection을 직접 만들어(check_same_thread=False로
Streamlit의 멀티스레드 실행 모델에서도 안전하게) SqliteSaver 생성자에 넘기는
방식을 택했습니다.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import DATA_DIR

_DB_PATH = str(DATA_DIR / "checkpoints.sqlite")


@lru_cache(maxsize=1)
def get_checkpointer() -> SqliteSaver:
    """프로세스 전체에서 재사용되는 단일 SqliteSaver 인스턴스를 반환한다."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)
