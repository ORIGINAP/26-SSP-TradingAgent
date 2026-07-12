"""
[역할] 이 그래프가 사용하는 모든 Tool을 한 곳에서 import할 수 있게 모아주는 패키지 진입점.

요구사항: "최소 2개 이상의 Tool"을 자율적으로 선택·실행 → 여기서는 4개를 제공합니다.
    1) get_macro_indicators   : 매크로 지표 조회 (대시보드용 + 자유질의용 겸용)
    2) get_sector_performance : 주도 섹터 조회 (대시보드용 + 자유질의용 겸용)
    3) search_market_news     : 뉴스/웹 검색 (대시보드 센티먼트용 + 자유질의 RAG 보강용)
    4) get_stock_quote        : 특정 종목 시세 조회 (자유질의 전용, 예: "삼성전자 지금 어때?")

ALL_TOOLS 리스트는 app/graph/nodes/agent.py 에서 `llm.bind_tools(ALL_TOOLS)` 형태로
LLM에 통째로 bind 되어, "자연어 요청 → LLM이 어떤 도구를 쓸지 스스로 판단" 하는
Tool-calling Agent 패턴의 재료가 됩니다.
"""

from app.tools.macro_tool import get_macro_indicators
from app.tools.news_tool import search_market_news
from app.tools.sector_tool import get_sector_performance
from app.tools.stock_quote_tool import get_stock_quote

ALL_TOOLS = [get_macro_indicators, get_sector_performance, search_market_news, get_stock_quote]
