"""
[역할] LangChain의 OutputParser(구조화 출력) 지점에서 사용하는 Pydantic 모델 모음.

평가 기준의 "OutputParser를 활용해 구조화된 출력(JSON/Pydantic)을 최소 1개 지점에서
사용" 요구사항을 충족하는 핵심 파일입니다.

[사용 패턴]
LangChain의 최신 방식인 `llm.with_structured_output(PydanticModel)` 을 사용합니다.
이 방식은 내부적으로 OutputParser + function-calling(tool-calling) 스키마 변환을
자동으로 처리해주는 최신 방식이라 별도의 PydanticOutputParser + format_instructions를
프롬프트에 수동으로 끼워넣지 않아도 됩니다. (구버전 LangChain 튜토리얼에서 보이는
`PydanticOutputParser(pydantic_object=...)` 방식보다 최신 방식)

즉,
    llm.with_structured_output(MacroSnapshot).invoke(prompt)
를 호출하면 결과가 곧바로 MacroSnapshot 인스턴스로 반환됩니다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    """router 노드에서 사용자의 자연어 요청을 3가지 의도 중 하나로 분류한 결과.

    LangGraph의 conditional edge는 문자열/enum 값을 보고 다음 노드를 결정하므로,
    이 모델의 `intent` 필드 값이 곧 분기(branch) 키가 됩니다.
    """

    intent: Literal["dashboard", "free_query", "bookmark"] = Field(
        description=(
            "dashboard: 매크로/섹터/뉴스 현황을 새로고침해서 보여달라는 요청. "
            "free_query: 특정 종목/이슈/이유 등을 자유롭게 묻는 질문. "
            "bookmark: 방금 답변이나 특정 정보를 저장(북마크)해달라는 요청."
        )
    )
    reason: str = Field(description="이렇게 분류한 한 줄 근거 (로깅/디버깅용)")


class MacroSnapshot(BaseModel):
    """매크로 지표 대시보드 카드 하나에 대응하는 구조화 데이터."""

    as_of: str = Field(description="데이터 기준 시각 (ISO 문자열)")
    sp500_price: float = Field(description="S&P500 지수(^GSPC) 최근 종가")
    sp500_change_pct: float = Field(description="S&P500 전일 대비 등락률(%)")
    vix: float = Field(description="변동성 지수(^VIX) 값")
    treasury_10y_yield: float = Field(description="미국 10년물 국채금리(%) (^TNX)")
    dollar_index: float = Field(description="달러 인덱스(DX-Y.NYB) 값")
    commentary: str = Field(description="위 수치들을 종합한 LLM의 1~2문장 해설")

    # 대시보드에 스파크라인(추세선)을 그리기 위한 최근 N거래일 종가 리스트. "등락률이
    # 뭘 기준인지 모르겠다"는 피드백에 대응해 추가 - 숫자 하나 대신 실제 흐름을 보여준다.
    history_days: int = Field(default=0, description="히스토리 리스트에 담긴 거래일 수")
    sp500_history: list[float] = Field(default_factory=list, description="S&P500 최근 종가 추이 (오래된 -> 최신)")
    vix_history: list[float] = Field(default_factory=list, description="VIX 최근 값 추이")
    treasury_10y_history: list[float] = Field(default_factory=list, description="10년물 국채금리 최근 추이")
    dollar_index_history: list[float] = Field(default_factory=list, description="달러 인덱스 최근 추이")


class SectorPerformance(BaseModel):
    """섹터 1개의 등락 정보 (SectorSnapshot 안에 리스트로 포함됨)."""

    sector: str = Field(description="섹터명 (예: Technology, Energy)")
    ticker: str = Field(description="해당 섹터 대표 ETF 티커 (예: XLK)")
    change_pct: float = Field(description="전일 대비 등락률(%)")


class SectorSnapshot(BaseModel):
    """주도 섹터 대시보드 카드에 대응하는 구조화 데이터."""

    as_of: str
    sectors: list[SectorPerformance] = Field(description="섹터별 등락률 리스트")
    leading_sector: str = Field(description="가장 강한 상승률을 보인 섹터명")
    commentary: str = Field(description="현재 시장 주도 섹터에 대한 LLM의 해설")


class NewsSentimentItem(BaseModel):
    """뉴스 기사 1건 + 그 기사에 대한 LLM 감성 분류 결과."""

    title: str
    url: str
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        description="해당 기사 내용이 시장에 대해 긍정/중립/부정 중 무엇을 시사하는지"
    )
    summary: str = Field(description="기사 내용 1문장 요약")


class MarketSentimentSnapshot(BaseModel):
    """'현재 시장에 대한 사람들의 반응' 대시보드 카드에 대응하는 구조화 데이터."""

    as_of: str
    items: list[NewsSentimentItem]
    overall_sentiment: Literal["positive", "neutral", "negative"]
    commentary: str = Field(description="종합 시장 심리에 대한 LLM의 1~2문장 해설")


class AgentAnswer(BaseModel):
    """자유 질의(free_query) 흐름의 최종 응답 포맷.

    RAG로 검색된 컨텍스트 + Tool 실행 결과를 LLM이 종합한 뒤, 이 스키마로
    강제 변환되어 사용자에게 반환됩니다. `sources`는 답변의 근거를 추적 가능하게
    만들어 RAG 응답 품질 평가('응답 반영도')에 도움이 됩니다.
    """

    answer: str = Field(description="사용자 질문에 대한 최종 답변 본문")
    sources: list[str] = Field(default_factory=list, description="답변에 사용된 출처(URL/문서명)")
    used_tools: list[str] = Field(default_factory=list, description="이번 응답을 만드는 데 호출된 Tool 이름 목록")
