"""
[역할] 속도 제한(rate limit) 미들웨어의 상태 저장소.

세션(session_id)별로 최근 N초 동안 몇 번 요청했는지를 세어, 과도한 요청으로
LLM/외부 API 비용이 폭증하는 것을 막습니다. 데모/평가용 프로젝트라 별도 Redis 없이
프로세스 메모리(dict)에 저장하는 가장 단순한 형태(in-memory token bucket 유사 구현)로
구현했습니다. (README 한계점: 프로세스 재시작 시 초기화됨, 다중 인스턴스 배포 시
카운트가 공유되지 않음 -> 실서비스라면 Redis 등 외부 저장소로 교체 필요)
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

_WINDOW_SECONDS = 60
_MAX_REQUESTS_PER_WINDOW = 20


class SessionRateLimiter:
    def __init__(self, window_seconds: int = _WINDOW_SECONDS, max_requests: int = _MAX_REQUESTS_PER_WINDOW):
        self._window_seconds = window_seconds
        self._max_requests = max_requests
        self._history: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, session_id: str) -> bool:
        """이번 요청을 허용해도 되면 True, 한도를 넘었으면 False를 반환하며 기록도 남긴다."""
        now = time.time()
        history = self._history[session_id]

        # 윈도우(예: 60초) 밖으로 벗어난 오래된 기록은 버린다.
        while history and now - history[0] > self._window_seconds:
            history.popleft()

        if len(history) >= self._max_requests:
            return False

        history.append(now)
        return True


# 프로세스 전체에서 공유되는 단일 인스턴스 (guardrail 노드가 이걸 사용)
rate_limiter = SessionRateLimiter()
