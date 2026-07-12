"""
[역할] Tool #1 - 매크로 지표 조회.

[사용 패턴] LangChain의 `@tool` 데코레이터로 일반 Python 함수를 "LLM이 호출 가능한
도구"로 변환합니다. 함수의 docstring이 곧 LLM에게 전달되는 "이 도구는 언제 쓰는가"
설명이 되므로, docstring을 사람이 아니라 LLM 독자를 염두에 두고 씁니다.

[데이터 소스] FRED 같은 공식 거시경제 API는 별도 키 발급이 필요해 오늘 마감 기준
설치 부담을 줄이려 제외했고, 대신 시장이 실시간으로 반영하는 매크로 프록시 지표를
yfinance(무료, 키 불필요)로 가져옵니다:
    - ^GSPC   : S&P500 지수 (증시 전반)
    - ^VIX    : 변동성(공포) 지수
    - ^TNX    : 미국 10년물 국채금리
    - DX-Y.NYB: 달러 인덱스
(README 한계점에 "공식 FRED 연동은 향후 개선 과제"로 명시)
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.tools import tool

from app.tools._market_data import fetch_last_change_pct, fetch_recent_history

_TICKERS = {
    "sp500": "^GSPC",
    "vix": "^VIX",
    "treasury_10y": "^TNX",
    "dollar_index": "DX-Y.NYB",
}

_HISTORY_DAYS = 10


def _history_values(ticker: str) -> list[float]:
    """스파크라인용 최근 종가 리스트만 뽑아낸다 (날짜 라벨은 프론트에서 별도로 안 씀)."""
    hist = fetch_recent_history(ticker, days=_HISTORY_DAYS)
    return [v for _, v in hist] if hist else []


@tool
def get_macro_indicators() -> dict:
    """현재 미국 매크로 지표 스냅샷을 조회한다.

    S&P500 지수/등락률, VIX(변동성 지수), 10년물 국채금리, 달러 인덱스와 함께 각 지표의
    최근 10거래일 추이(히스토리)를 반환한다. "등락률이 뭘 기준인지 모르겠다"는 피드백에
    대응해, 대시보드가 숫자 하나만 보여주지 않고 실제 추세선을 그릴 수 있게 했다.
    사용자가 "지금 시장 전체적으로 어때?", "매크로 지표 보여줘", "금리/변동성 어떻게 돼?"
    처럼 시장 전반의 거시 상황을 물을 때 사용한다.
    """
    result: dict = {"as_of": datetime.now(timezone.utc).isoformat(), "history_days": _HISTORY_DAYS}

    sp500 = fetch_last_change_pct(_TICKERS["sp500"])
    result["sp500_price"], result["sp500_change_pct"] = sp500 if sp500 else (None, None)
    result["sp500_history"] = _history_values(_TICKERS["sp500"])

    vix = fetch_last_change_pct(_TICKERS["vix"])
    result["vix"] = vix[0] if vix else None
    result["vix_history"] = _history_values(_TICKERS["vix"])

    tnx = fetch_last_change_pct(_TICKERS["treasury_10y"])
    result["treasury_10y_yield"] = tnx[0] if tnx else None
    result["treasury_10y_history"] = _history_values(_TICKERS["treasury_10y"])

    dxy = fetch_last_change_pct(_TICKERS["dollar_index"])
    result["dollar_index"] = dxy[0] if dxy else None
    result["dollar_index_history"] = _history_values(_TICKERS["dollar_index"])

    return result
