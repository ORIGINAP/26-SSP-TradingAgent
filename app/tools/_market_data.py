"""
[역할] yfinance 호출 로직 공통 유틸. Tool이 아니라 Tool들이 재사용하는 "내부 헬퍼"입니다.

주의: 이 파일의 함수들은 @tool 데코레이터가 붙어있지 않습니다 = LLM에게 노출되지 않습니다.
LLM에게는 macro_tool.py / sector_tool.py 의 @tool 함수만 보이고, 그 함수들이 내부적으로
이 헬퍼를 호출하는 구조입니다. (Tool 인터페이스와 실제 구현을 분리 = 재사용성/가독성)
"""

from __future__ import annotations

import logging

import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_last_change_pct(ticker: str) -> tuple[float, float] | None:
    """티커의 (최근 종가, 전일 대비 등락률 %) 를 반환. 조회 실패 시 None.

    yfinance는 외부 API라 네트워크 문제로 언제든 실패할 수 있어서, 여기서 예외를
    삼키고 None을 반환합니다. 호출부(Tool)에서 None을 만나면 "해당 지표만 결측"으로
    처리하고 나머지 지표는 정상적으로 보여줍니다 (부분 실패가 전체 실패로 번지지 않도록).
    """
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty or len(hist) < 2:
            return None
        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        change_pct = (last_close - prev_close) / prev_close * 100
        return last_close, change_pct
    except Exception:  # noqa: BLE001 - 외부 API 실패는 폭넓게 잡아서 None으로 흡수
        logger.warning("yfinance 조회 실패: ticker=%s", ticker, exc_info=True)
        return None


def fetch_recent_history(ticker: str, days: int = 10) -> list[tuple[str, float]] | None:
    """최근 `days` 거래일치 (날짜, 종가) 리스트를 오래된 순으로 반환.

    "등락률이 뭘 기준으로 계산된 건지 모르겠다"는 피드백에 대응하기 위해 추가했다.
    대시보드에서 이 리스트로 스파크라인(추세선)을 그려서, 숫자 하나(전일 대비 %)가
    아니라 최근 며칠간의 실제 흐름을 보여준다. 주말/공휴일을 감안해 여유 있게
    `days + 5`일치를 요청한 뒤 뒤에서 `days`개만 잘라 쓴다.
    """
    try:
        hist = yf.Ticker(ticker).history(period=f"{days + 5}d")
        if hist.empty:
            return None
        hist = hist.tail(days)
        return [(idx.strftime("%m/%d"), float(close)) for idx, close in hist["Close"].items()]
    except Exception:  # noqa: BLE001 - 외부 API 실패는 폭넓게 잡아서 None으로 흡수
        logger.warning("yfinance 히스토리 조회 실패: ticker=%s", ticker, exc_info=True)
        return None
