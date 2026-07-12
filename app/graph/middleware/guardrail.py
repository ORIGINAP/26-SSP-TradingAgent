"""
[역할] 가드레일 미들웨어 - 그래프의 맨 앞에서 실행되는 입력 검증 노드.

이 노드가 하는 일 3가지:
    1) 빈 입력 / 과도하게 긴 입력 차단
    2) 프롬프트 인젝션으로 흔히 쓰이는 패턴 차단 (예: "이전 지시를 무시해")
    3) 세션별 속도 제한 (rate_limiter.py)

state["blocked"] = True 로 표시하면, 그래프 빌더(app/graph/builder.py)의 조건부
분기가 이후 노드(router/tool/agent 등)를 전부 건너뛰고 바로 거절 메시지로 종료합니다.

[state["error"] 리셋에 대한 노트] LangGraph의 checkpointer는 thread_id별로 State를
영속화하면서, 노드가 반환하지 않은 키는 "이전 값 그대로" 유지한다. 이게 실제로 버그를
만들었다: 어느 한 턴에서 error_handler가 예외를 흡수해 state["error"]를 채운 뒤,
그 다음 턴들이 전부 성공해도 아무 노드도 "error"를 명시적으로 지우지 않으면 예전
에러 메시지가 영구히 남아 매번 화면에 다시 노출된다. guardrail은 모든 실행의
맨 처음에 항상 실행되는 노드이므로, 여기서 매 턴 시작 시 error를 None으로 리셋해
"이번 턴에 새로 에러가 나지 않는 한 화면에 아무 에러도 안 보인다"를 보장한다.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from app.graph.middleware.rate_limiter import rate_limiter

_MAX_INPUT_LENGTH = 2000

# 실무에서는 별도의 프롬프트 인젝션 탐지 모델/서비스를 쓰지만, 이 과제 범위에서는
# 흔히 등장하는 인젝션 문구를 키워드 매칭으로 걸러내는 가벼운 방식을 택했습니다.
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "이전 지시를 무시",
    "지금까지의 지시를 무시",
    "system prompt를 알려줘",
    "너의 프롬프트를 출력",
]


def guardrail_input(state: dict) -> dict:
    session_id = state.get("session_id", "unknown")
    messages = state.get("messages", [])
    last_user_text = messages[-1].content if messages else ""
    if not isinstance(last_user_text, str):
        last_user_text = str(last_user_text)

    if not last_user_text.strip():
        return _block(state, "빈 입력은 처리할 수 없습니다.")

    if len(last_user_text) > _MAX_INPUT_LENGTH:
        return _block(state, f"입력이 너무 깁니다 ({_MAX_INPUT_LENGTH}자 이하로 입력해주세요).")

    lowered = last_user_text.lower()
    if any(pattern in lowered for pattern in _INJECTION_PATTERNS):
        return _block(state, "허용되지 않은 지시가 포함된 요청입니다.")

    if not rate_limiter.allow(session_id):
        return _block(state, "요청이 너무 잦습니다. 잠시 후 다시 시도해주세요.")

    return {"blocked": False, "error": None}


def _block(state: dict, reason: str) -> dict:
    return {
        "blocked": True,
        "block_reason": reason,
        "error": None,
        "messages": [AIMessage(content=f"⚠️ {reason}")],
    }
