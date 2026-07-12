"""
[역할] RAG "검색+증강" 노드 - 자유 질의(free_query) 흐름에서만 실행된다.

사용자의 마지막 질문으로 벡터스토어를 검색해 관련 문서를 찾고, 이를 프롬프트에
바로 넣을 수 있는 문자열로 만들어 state["rag_context"]에 저장한다. 이후
agent.py의 call_agent_llm 노드가 이 컨텍스트를 시스템 프롬프트에 포함시켜
"검색된 근거를 참고해서 답하라"고 LLM에게 지시한다 (RAG의 Augmented Generation 단계).
"""

from __future__ import annotations

from app.rag.retriever import format_context_for_prompt, retrieve_context


def retrieve_and_augment(state: dict) -> dict:
    messages = state.get("messages", [])
    query = str(messages[-1].content) if messages else ""

    docs = retrieve_context(query, k=4)
    return {"rag_context": format_context_for_prompt(docs)}
