"""
[역할] Tool #2 - 섹터별 등락률 조회 → "현재 시장의 주도 섹터"를 계산.

[데이터 소스] S&P500의 11개 GICS 섹터를 대표하는 State Street SPDR 섹터 ETF들을
yfinance로 조회합니다. (개별 종목 수백 개를 다 볼 필요 없이 섹터 ETF 1개씩만 보면
그 섹터의 대략적인 흐름을 알 수 있음 - 실무에서도 흔히 쓰는 방식)
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.tools import tool

from app.tools._market_data import fetch_last_change_pct

# 섹터명 -> 대표 SPDR 섹터 ETF 티커
_SECTOR_ETFS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Energy": "XLE",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


@tool
def get_sector_performance() -> dict:
    """현재 미국 증시의 섹터별 등락률과 주도 섹터를 조회한다.

    11개 GICS 섹터 대표 ETF의 전일 대비 등락률을 계산하고, 가장 강세인 섹터를
    leading_sector로 표시한다. 사용자가 "지금 어떤 섹터가 강해?", "주도주/주도 업종이
    뭐야?", "반도체 섹터 흐름 어때?" 처럼 섹터 로테이션을 물을 때 사용한다.
    """
    sectors: list[dict] = []
    for sector_name, ticker in _SECTOR_ETFS.items():
        data = fetch_last_change_pct(ticker)
        if data is None:
            continue  # 개별 섹터 조회 실패는 건너뛰고 나머지로 계속 진행 (부분 실패 허용)
        _, change_pct = data
        sectors.append({"sector": sector_name, "ticker": ticker, "change_pct": change_pct})

    leading_sector = max(sectors, key=lambda s: s["change_pct"])["sector"] if sectors else None

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "sectors": sectors,
        "leading_sector": leading_sector,
    }
