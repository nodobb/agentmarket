"""
Rate limiting shared across the application.

Agent endpoints are keyed by API key when present so one busy agent cannot
exhaust the limit for everyone behind the same IP (and vice versa).
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from agentmarket.utils.config import settings


def rate_limit_key(request: Request) -> str:
    api_key = request.headers.get("X-Agent-API-Key")
    if api_key:
        return f"agent:{api_key}"
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key)

AGENT_RATE_LIMIT = f"{settings.RATE_LIMIT_PER_MINUTE}/minute"
LOGIN_RATE_LIMIT = "10/minute"
