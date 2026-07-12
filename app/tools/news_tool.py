"""
[역할] Tool #3 - 뉴스/웹 검색. 두 곳에서 재사용됩니다.
    1) 대시보드의 "시장 반응(뉴스 센티먼트)" 카드 생성 (app/graph/nodes/news.py)
    2) RAG 색인 대상 원문 수집 (app/rag/ingest.py 가 이 결과를 벡터스토어에 적재)
    3) 자유 질의 중 LLM이 최신 이슈를 찾아야 할 때 (app/graph/nodes/agent.py)

[사용 패턴] Tavily는 LLM 에이전트를 위해 설계된 검색 API로, LangChain 공식 통합
패키지(langchain-tavily)가 있어 이번 프로젝트의 "웹 검색 Tool" 표준 선택지로
많이 쓰입니다. 여기서는 그 결과를 우리 스키마(app/schemas)에 맞게 가공해서
반환하는 얇은 래퍼를 만들었습니다.
"""

from __future__ import annotations

import logging
import os

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# Tavily의 topic="finance"만으로는 한국어 질의에서 일반 뉴스(사회/정치/날씨 등)가 섞여
# 들어오는 걸 실제로 겪었다 (예: "폭염과 집중호우", 경찰 수사 관련 기사가 대시보드 뉴스
# 카드에 노출됨). topic 필터는 "느슨한 가중치"에 가깝고 강제 제외가 아니라서, 검증된
# 금융 매체로 도메인 자체를 제한해 확실하게 걸러낸다.
_FINANCE_DOMAINS = [
    "finance.yahoo.com",
    "reuters.com",
    "bloomberg.com",
    "cnbc.com",
    "marketwatch.com",
    "wsj.com",
    "investing.com",
]


def _tavily_search(query: str, max_results: int, include_domains: list[str] | None = None) -> list[dict]:
    """Tavily 클라이언트 호출부. 패키지 미설치/키 누락 시 빈 리스트로 저하(degrade)."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.warning("TAVILY_API_KEY가 없어 뉴스 검색을 건너뜁니다.")
        return []
    try:
        from langchain_tavily import TavilySearch

        kwargs = {"max_results": max_results, "topic": "finance"}
        if include_domains:
            kwargs["include_domains"] = include_domains
        client = TavilySearch(**kwargs)
        raw = client.invoke({"query": query})
        # langchain-tavily는 {"results": [...]} 형태를 반환
        return raw.get("results", []) if isinstance(raw, dict) else []
    except Exception:  # noqa: BLE001 - 외부 검색 API 실패가 그래프 전체를 죽이면 안 됨
        logger.warning("Tavily 검색 실패: query=%s", query, exc_info=True)
        return []


def _normalize(results: list[dict]) -> list[dict]:
    """Tavily 원본 응답을 title/url/content 3개 필드로만 정리한다 (RAG 적재/렌더링 공통 형식)."""
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        }
        for item in results
    ]


def fetch_finance_headlines(query: str, max_results: int = 5) -> list[dict]:
    """대시보드 뉴스 카드 전용 - 검증된 금융 매체로 도메인을 제한한 검색.

    LLM에게 노출되는 @tool이 아니라, app/graph/nodes/news.py가 직접 호출하는 내부
    함수다. 자유 질의용 search_market_news는 특정 종목/이슈를 물을 때 도메인을 좁히면
    오히려 답을 놓칠 수 있어 제한을 두지 않고, "시장 전반 브리핑" 목적인 대시보드만
    엄격하게 금융 매체로 한정했다.
    """
    return _normalize(_tavily_search(query, max_results, include_domains=_FINANCE_DOMAINS))


@tool
def search_market_news(query: str) -> list[dict]:
    """주식 시장/특정 종목/섹터와 관련된 최신 뉴스를 웹에서 검색한다.

    Args:
        query: 검색어. 예) "S&P500 오늘 시황", "반도체 섹터 뉴스", "삼성전자 실적"

    Returns:
        각 기사에 대해 title/url/content(발췌)를 담은 딕셔너리 리스트.
    """
    return _normalize(_tavily_search(query, max_results=5))
