"""Operational health endpoints for process and dependency checks."""

import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


logger = logging.getLogger(__name__)


@require_GET
def live(request):
    """Return 200 when the Django process can serve requests."""
    return JsonResponse({"status": "ok"})


def _database_check():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        if result != (1,):
            raise RuntimeError("unexpected database response")
    except Exception as exc:  # pragma: no cover - exact driver errors vary
        logger.warning("database readiness check failed: %s", type(exc).__name__)
        return {"status": "error", "error": type(exc).__name__}
    return {"status": "ok"}


def _cache_check():
    try:
        # RedisCache exposes the configured client; ping avoids changing cache data.
        cache._cache.get_client(write=False).ping()
    except Exception as exc:  # pragma: no cover - exact driver errors vary
        logger.warning("cache readiness check failed: %s", type(exc).__name__)
        return {"status": "error", "error": type(exc).__name__}
    return {"status": "ok"}


@require_GET
def ready(request):
    """Return 200 only when the database and cache are reachable."""
    checks = {
        "database": _database_check(),
        "cache": _cache_check(),
    }
    is_ready = all(check["status"] == "ok" for check in checks.values())
    return JsonResponse(
        {"status": "ok" if is_ready else "not_ready", "checks": checks},
        status=200 if is_ready else 503,
    )
