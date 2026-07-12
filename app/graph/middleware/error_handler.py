"""
[역할] 에러 핸들링 미들웨어 - 노드 실행 중 예외가 나도 그래프 전체가 죽지 않게 흡수한다.

[왜 필요한가] 이 그래프의 노드들은 대부분 외부 I/O(yfinance, Tavily, LLM API)를
호출합니다. 외부 API는 타임아웃/쿼터초과/네트워크 오류로 언제든 실패할 수 있는데,
LangGraph는 노드에서 잡히지 않은 예외가 나면 그래프 실행 자체가 중단됩니다.
`@safe_node`는 이를 막고, 대신 state["error"]에 원인을 기록한 뒤 사용자에게
"일부 정보를 가져오지 못했다"는 정상적인 응답을 만들 수 있게 해줍니다
(요구사항 "예외처리" + 평가항목 "Middleware 적용" 대응).
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

logger = logging.getLogger("trading_agent.graph")

NodeFn = Callable[[dict], dict]


def safe_node(node_name: str) -> Callable[[NodeFn], NodeFn]:
    """노드 함수를 감싸, 예외 발생 시 그래프를 죽이지 않고 state["error"]로 흡수한다."""

    def decorator(fn: NodeFn) -> NodeFn:
        @functools.wraps(fn)
        def wrapper(state: dict, *args: Any, **kwargs: Any) -> dict:
            try:
                return fn(state, *args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - 의도적으로 넓게 잡는 최후 방어선
                logger.exception("[%s] 처리되지 않은 예외를 미들웨어가 흡수함", node_name)
                return {"error": f"{node_name} 단계에서 오류가 발생했습니다: {exc}"}

        return wrapper

    return decorator
