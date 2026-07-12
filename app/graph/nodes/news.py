"""
[역할] 대시보드의 "시장에 대한 사람들의 반응(뉴스 센티먼트)" 카드를 만드는 노드.

macro.py/sector.py와 반대로, 여기서는 `with_structured_output(MarketSentimentSnapshot)`
을 씁니다. 이유: 기사별 긍정/중립/부정 판단과 요약은 순수 언어 이해 작업이라
Tool(검색 API)이 대신해줄 수 없고, 정확히 LLM이 해야 하는 "판단"이기 때문입니다.
(macro/sector와 대비되는 설계 근거는 macro.py 상단 주석 참고)

또한 이 노드가 가져온 뉴스는 app/rag/ingest.py를 통해 벡터스토어에도 함께
적재됩니다 -> 대시보드에서 본 뉴스가 이후 자유 질의(RAG)의 검색 대상이 됩니다.
"""

from __future__ import annotations

from app.llm import with_fallback
from app.rag.ingest import ingest_news_articles
from app.schemas.models import MarketSentimentSnapshot
from app.tools.news_tool import fetch_finance_headlines

# 한국어 쿼리("오늘 미국 증시 시황 및 주요 뉴스")로 검색했더니 폭염/집중호우 같은 일반
# 뉴스, 사회면 기사가 섞여 들어오는 문제를 실제로 겪었다. Tavily는 영어 금융 용어에
# 대한 색인이 훨씬 촘촘해서 쿼리를 영어로 바꾸고, fetch_finance_headlines()로 도메인도
# 검증된 금융 매체로 제한했다 (app/tools/news_tool.py 참고).
_DEFAULT_QUERY = "US stock market today S&P 500 Dow Nasdaq news"


def run_news_node(state: dict) -> dict:
    articles = fetch_finance_headlines(_DEFAULT_QUERY)

    # 대시보드에서 읽은 뉴스를 RAG 지식베이스에도 함께 쌓는다 (일반 지식 RAG 적재 경로).
    ingest_news_articles(articles)

    if not articles:
        empty = MarketSentimentSnapshot(as_of="", items=[], overall_sentiment="neutral", commentary="수집된 뉴스가 없습니다.")
        return {"news_snapshot": empty.model_dump()}

    llm = with_fallback(lambda m: m.with_structured_output(MarketSentimentSnapshot))
    snapshot: MarketSentimentSnapshot = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "아래 뉴스 기사 목록(영문)을 보고 각 기사의 감성(positive/neutral/negative)과 "
                    "1문장 한국어 요약을 만들고, 전체 종합 심리(overall_sentiment)와 한국어 해설을 "
                    "작성해라. summary와 commentary 필드는 반드시 한국어로 작성한다 (원문이 영어라도 "
                    "번역·요약해서 한국어로 낼 것). sentiment/overall_sentiment 값 자체는 영어 "
                    "리터럴(positive/neutral/negative)을 그대로 사용한다."
                ),
            },
            {"role": "user", "content": str(articles)},
        ]
    )
    return {"news_snapshot": snapshot.model_dump()}
