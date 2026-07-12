"""
[역할] 대시보드의 "주도 섹터" 카드를 만드는 노드. 설계 사상은 macro.py와 동일
(숫자는 Tool 결과를 그대로 신뢰하고, LLM은 해설 문장만 생성).
"""

from __future__ import annotations

from app.llm import with_fallback
from app.schemas.models import SectorPerformance, SectorSnapshot
from app.tools.sector_tool import get_sector_performance


def run_sector_node(state: dict) -> dict:
    raw = get_sector_performance.invoke({})

    llm = with_fallback(lambda m: m)
    commentary = llm.invoke(
        [
            {
                "role": "system",
                "content": (
                    "너는 섹터 로테이션 애널리스트다. 주어진 섹터별 등락률을 보고 "
                    "현재 시장을 주도하는 섹터와 그 배경 추정을 한국어 1~2문장으로 써라."
                ),
            },
            {"role": "user", "content": str(raw)},
        ]
    ).content

    sectors = [SectorPerformance(**s) for s in raw.get("sectors", [])]
    snapshot = SectorSnapshot(
        as_of=raw.get("as_of", ""),
        sectors=sectors,
        leading_sector=raw.get("leading_sector") or "N/A",
        commentary=str(commentary),
    )
    return {"sector_snapshot": snapshot.model_dump()}
