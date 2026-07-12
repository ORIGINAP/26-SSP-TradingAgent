"""
[역할] Tool #4 - 개별 종목 시세 조회. 대시보드가 아니라 "자유 질의" 흐름에서만 쓰입니다.

예: 사용자가 "삼성전자 지금 어때?", "AAPL 실적 대비 주가 어때?" 라고 물으면
LLM이 이 Tool을 스스로 호출해서 실제 수치를 가져온 뒤 답변에 반영합니다.
(하드코딩된 종목 리스트가 아니라 ticker를 LLM이 문맥에서 추론해서 넘겨줌 = Tool
argument를 LLM이 채우는 전형적인 Tool-calling 패턴)

한국 종목은 야후 파이낸스 표기 규칙상 티커 뒤에 코드가 붙습니다
(예: 삼성전자 -> "005930.KS", 카카오 -> "035720.KQ"). 이 매핑까지 완벽히 자동화하지는
못했고, LLM이 알고 있는 상식 선에서 티커를 채우도록 docstring에 안내만 넣었습니다.
(README 한계점에 명시)
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.tools._market_data import fetch_last_change_pct


@tool
def get_stock_quote(ticker: str) -> dict:
    """특정 종목 하나의 최근 종가와 전일 대비 등락률을 조회한다.

    Args:
        ticker: yfinance 형식의 종목 티커. 미국 종목은 그대로(예: "AAPL", "NVDA"),
            한국 종목은 코스피는 ".KS", 코스닥은 ".KQ" 접미사를 붙인다
            (예: 삼성전자 -> "005930.KS").
    """
    data = fetch_last_change_pct(ticker)
    if data is None:
        return {"ticker": ticker, "error": "시세 조회에 실패했습니다. 티커를 확인해주세요."}
    price, change_pct = data
    return {"ticker": ticker, "price": price, "change_pct": change_pct}
