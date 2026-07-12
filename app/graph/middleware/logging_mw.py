"""
[역할] 로깅 미들웨어 - 모든 그래프 노드의 진입/종료/소요시간/에러 여부를 구조화 로그로 남긴다.

[사용 패턴] 데코레이터 패턴. `@log_node("router")` 를 노드 함수에 씌우면, 원래
노드 로직은 건드리지 않고 앞뒤로 로깅 코드가 자동으로 실행됩니다 (관심사 분리).
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("trading_agent.graph")

NodeFn = Callable[[dict], dict]


def log_node(node_name: str) -> Callable[[NodeFn], NodeFn]:
    """노드 함수를 감싸 실행 로그(시작/종료/소요시간)를 남기는 데코레이터를 반환한다."""

    def decorator(fn: NodeFn) -> NodeFn:
        @functools.wraps(fn)
        def wrapper(state: dict, *args: Any, **kwargs: Any) -> dict:
            session_id = state.get("session_id", "unknown")
            started = time.perf_counter()
            logger.info("[%s] 진입 (session=%s)", node_name, session_id)
            try:
                result = fn(state, *args, **kwargs)
                elapsed_ms = (time.perf_counter() - started) * 1000
                logger.info("[%s] 종료 (%.1fms)", node_name, elapsed_ms)
                return result
            except Exception:
                elapsed_ms = (time.perf_counter() - started) * 1000
                logger.exception("[%s] 예외 발생 (%.1fms)", node_name, elapsed_ms)
                raise  # 여기서는 로깅만 하고, 실제 예외 처리는 error_handler.safe_node 몫

        return wrapper

    return decorator
