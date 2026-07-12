"""
[역할] RAG "검색(retrieve)" 단계 - 사용자 질문과 의미적으로 가까운 문서를 벡터스토어에서 찾는다.
"""

from __future__ import annotations

from langchain_core.documents import Document

from app.rag.vectorstore import get_vectorstore


def retrieve_context(query: str, k: int = 4) -> list[Document]:
    """질의와 유사도가 높은 문서 k개를 반환한다 (뉴스 청크 + 북마크 통합 검색).

    similarity_search를 사용 (MMR도 고려했지만, 카드형 짧은 컨텍스트가 대부분이라
    다양성 확보보다는 순수 관련도 우선이 이 서비스 성격에 더 맞았습니다).
    """
    vectorstore = get_vectorstore()
    try:
        return vectorstore.similarity_search(query, k=k)
    except Exception:  # noqa: BLE001 - 컬렉션이 비어있는 초기 상태 등에서도 죽지 않게
        return []


def format_context_for_prompt(docs: list[Document]) -> str:
    """검색된 Document 리스트를 LLM 프롬프트에 바로 붙여넣을 수 있는 문자열로 변환."""
    if not docs:
        return "(검색된 참고 자료 없음)"

    blocks = []
    for i, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown")
        title = doc.metadata.get("title") or doc.metadata.get("label") or ""
        blocks.append(f"[{i}] ({source}) {title}\n{doc.page_content}")
    return "\n\n".join(blocks)
