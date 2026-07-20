"""비용·인증 관련 시민 API를 보호하는 프로세스 단위 고정 윈도우 제한기.

해커톤 단일 프로세스 배포용 최소 안전장치다. 다중 워커/다중 인스턴스 운영으로
전환할 때는 Redis 기반 공용 제한기로 교체해야 한다.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
MAX_TRACKED_CLIENT_BUCKETS = int(os.environ.get("RATE_LIMIT_MAX_CLIENT_BUCKETS", "10000"))

_LIMITS: tuple[tuple[str, int], ...] = (
    ("/api/v1/citizen/auth/", int(os.environ.get("AUTH_RATE_LIMIT_PER_MINUTE", "30"))),
    ("/api/v1/citizen/diagnose", int(os.environ.get("DIAGNOSE_RATE_LIMIT_PER_MINUTE", "60"))),
)

_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = Lock()


def _limit_for_path(path: str) -> tuple[str, int] | None:
    if path.endswith("/explanation") and path.startswith("/api/v1/citizen/"):
        return "explanation", int(os.environ.get("EXPLANATION_RATE_LIMIT_PER_MINUTE", "20"))
    for prefix, limit in _LIMITS:
        if path.startswith(prefix):
            return path, limit
    return None


class CitizenRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rule = _limit_for_path(request.url.path)
        if rule is None:
            return await call_next(request)

        bucket_name, limit = rule
        client_host = request.client.host if request.client else "unknown"
        key = (client_host, bucket_name)
        now = time.monotonic()

        with _lock:
            if key not in _events and len(_events) >= MAX_TRACKED_CLIENT_BUCKETS:
                # 공격자가 수많은 연결 주소로 버킷을 만들어 메모리를 무한 증가시키는
                # 상황을 막는다. 가장 오래 삽입된 버킷 하나를 제한적으로 축출한다.
                _events.pop(next(iter(_events)))
            bucket = _events[key]
            cutoff = now - WINDOW_SECONDS
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(WINDOW_SECONDS - (now - bucket[0])))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."},
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)

        return await call_next(request)
