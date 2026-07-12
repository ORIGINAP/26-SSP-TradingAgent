"""
[역할] 대시보드의 "매크로 지표" 카드를 만드는 노드.

[설계 노트: 왜 with_structured_output을 여기서는 안 쓰는가]
매크로 수치(S&P500 가격, VIX 값 등)는 이미 Tool(yfinance)이 정확한 숫자로
반환합니다. 이 숫자를 굳이 LLM에게 다시 "구조화 출력으로 뽑아내라"고 시키면,
LLM이 숫자를 잘못 옮겨 적을(hallucinate) 위험만 추가될 뿐 얻는 게 없습니다.
그래서 숫자 필드는 Tool 결과를 그대로 MacroSnapshot에 채우고, LLM에게는
"이 숫자들을 보고 자연어로 1~2문장 해설을 써라"는, LLM이 진짜 잘하는 일만
맡깁니다. (뉴스 감성 분류처럼 "판단"이 필요한 news.py 노드는 반대로
with_structured_output을 사용합니다 - 대비해서 보면 각 패턴을 언제 쓰는지
드러나도록 의도했습니다.)
"""

from __future__ import annotations

from app.llm import with_fallback
from app.schemas.models import MacroSnapshot
from app.tools.macro_tool import get_macro_indicators


def run_macro_node(state: dict) -> dict:
    raw = get_macro_indicators.invoke({})

    # 해설 생성용 프롬프트에는 스파크라인용 일별 히스토리를 빼고 요약 수치만 넘긴다.
    # (LLM이 1~2문장 해설을 쓰는 데 10일치 원본 시계열은 불필요하게 프롬프트만 키운다)
    summary_only = {k: v for k, v in raw.items() if not k.endswith("_history")}

    llm = with_fallback(lambda m: m)
    commentary = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "너는 매크로 애널리스트다. 주어진 수치를 근거로 현재 거시 환경을 "
                    "한국어 1~2문장으로 간결하게 해설해라. 숫자를 새로 만들어내지 말고 "
                    "주어진 값만 근거로 삼아라."
                ),
            },
            {"role": "user", "content": str(summary_only)},
        ]
    ).content

    snapshot = MacroSnapshot(
        as_of=raw.get("as_of", ""),
        sp500_price=raw.get("sp500_price") or 0.0,
        sp500_change_pct=raw.get("sp500_change_pct") or 0.0,
        vix=raw.get("vix") or 0.0,
        treasury_10y_yield=raw.get("treasury_10y_yield") or 0.0,
        dollar_index=raw.get("dollar_index") or 0.0,
        commentary=str(commentary),
        history_days=raw.get("history_days") or 0,
        sp500_history=raw.get("sp500_history") or [],
        vix_history=raw.get("vix_history") or [],
        treasury_10y_history=raw.get("treasury_10y_history") or [],
        dollar_index_history=raw.get("dollar_index_history") or [],
    )
    return {"macro_snapshot": snapshot.model_dump()}
