"""
[역할] RAG "적재(ingest)" 단계 - 원문을 청크로 쪼개고(chunk) 임베딩해서 벡터스토어에 넣는다.

RAG 파이프라인은 보통 (1)적재 (2)검색 (3)생성 3단계로 나뉘는데, 이 파일은 (1)을 담당하고
retriever.py가 (2)를, LLM 호출부(agent 노드)가 (3)을 담당합니다.

이 프로젝트에는 두 개의 적재 경로가 있습니다.
    - ingest_news_articles(): 뉴스 검색 결과를 정기적으로/필요 시 적재 (일반 지식 RAG)
    - ingest_bookmark()     : 사용자가 명시적으로 저장을 요청한 답변 1건을 즉시 적재 (개인화 RAG)
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.vectorstore import get_vectorstore

# 뉴스 기사는 보통 문단 단위로 의미가 끊기므로 500자 청크 + 50자 overlap이면
# 검색 정확도와 청크 개수(=임베딩 호출 비용) 사이에서 합리적인 절충점이 됩니다.
_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)


def ingest_news_articles(articles: list[dict]) -> int:
    """뉴스 검색 결과(search_market_news Tool의 반환값)를 벡터스토어에 적재한다.

    Args:
        articles: [{"title": ..., "url": ..., "content": ...}, ...]

    Returns:
        실제로 적재된 청크 개수.
    """
    if not articles:
        return 0

    documents: list[Document] = []
    for article in articles:
        text = f"{article.get('title', '')}\n{article.get('content', '')}".strip()
        if not text:
            continue
        for chunk in _splitter.split_text(text):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": "news",
                        "title": article.get("title", ""),
                        "url": article.get("url", ""),
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            )

    if not documents:
        return 0

    get_vectorstore().add_documents(documents)
    return len(documents)


def ingest_bookmark(content: str, *, session_id: str, label: str = "") -> None:
    """사용자가 '북마크'로 저장을 요청한 텍스트 1건을 즉시 벡터스토어에 적재한다.

    뉴스 적재와 달리 청크 분할을 하지 않는 이유: 북마크는 이미 AI가 요약/정리한
    짧은 답변 단위이기 때문에, 쪼개면 오히려 문맥이 끊겨 검색 품질이 떨어집니다.
    """
    document = Document(
        page_content=content,
        metadata={
            "source": "bookmark",
            "session_id": session_id,
            "label": label,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    get_vectorstore().add_documents([document])
