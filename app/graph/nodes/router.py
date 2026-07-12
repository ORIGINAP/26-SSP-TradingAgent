"""
[역할] router 노드 - 사용자의 자연어 요청을 3가지 의도로 분류한다.

이 노드의 출력(state["intent"])이 app/graph/builder.py의 conditional edge가
"다음에 어느 노드로 갈지" 결정하는 기준값이 됩니다. 즉, 이 파일이 LangGraph
요구사항 "최소 1개 이상의 조건부 분기"의 분류기 역할을 합니다.

[사용 패턴] `llm.with_structured_output(RouteDecision)` - OutputParser 지점 중 하나.
자유서술형 답변 대신 Literal 타입 필드를 강제해서, 이후 코드가 문자열 파싱 없이
안전하게 분기할 수 있게 합니다.
"""

from __future__ import annotations

from app.llm import with_fallback
from app.schemas.models import RouteDecision

_BOOKMARK_PREFIX = "__bookmark__:"  # 프론트엔드의 "🔖 북마크" 버튼이 보내는 특수 접두사

_SYSTEM_PROMPT = (
    "너는 주식 트레이딩 어시스턴트의 라우터다. 사용자의 마지막 메시지를 보고 "
    "intent를 dashboard / free_query / bookmark 중 하나로 분류해라.\n"
    "\n"
    "- dashboard: 매크로 지표, 섹터 현황, 시장 전반 요약을 새로고침해 달라는 요청\n"
    "- bookmark: 사용자가 지금 이 순간 '저장해줘/북마크해줘/기억해둬'처럼 직전 답변을 "
    "저장하라고 **명령**하는 경우에만 해당한다.\n"
    "- free_query: 그 외 전부. 특정 종목/섹터/이슈 질문뿐 아니라, 문장에 '북마크'나 "
    "'기억'이라는 단어가 들어있어도 실제로는 정보를 묻거나 조회하는 질문이면 반드시 "
    "free_query로 분류한다.\n"
    "\n"
    "판별 기준은 단 하나다: 사용자가 지금 '저장해라'라고 명령하고 있는가? "
    "의문문/질문이면 절대 bookmark가 아니다 (bookmark라는 단어가 나와도 마찬가지).\n"
    "\n"
    "예시:\n"
    "'이거 북마크해줘' -> bookmark\n"
    "'방금 답변 저장해' -> bookmark\n"
    "'북마크에 뭐 저장돼있어?' -> free_query\n"
    "'아까 하이닉스 말한거 기억해?' -> free_query\n"
    "'저장한 내용 알려줘' -> free_query\n"
    "'삼성전자 지금 어때?' -> free_query\n"
    "'대시보드 새로고침해줘' -> dashboard"
)


def route_intent(state: dict) -> dict:
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    last_text = last_message.content if last_message else ""

    # UI에서 명시적으로 북마크 버튼을 누른 경우, 굳이 LLM 호출로 의도를 추측할
    # 필요가 없으므로 여기서 바로 결정한다 (불필요한 API 호출/지연 절약).
    if isinstance(last_text, str) and last_text.startswith(_BOOKMARK_PREFIX):
        return {"intent": "bookmark", "bookmark_content": last_text[len(_BOOKMARK_PREFIX):]}

    # with_fallback: 주 모델(OpenRouter 등)이 실패하면 보조 모델로 자동 전환 (app/llm.py 참고)
    llm = with_fallback(lambda m: m.with_structured_output(RouteDecision))
    decision: RouteDecision = llm.invoke(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": str(last_text)},
        ]
    )
    return {"intent": decision.intent}
