"""Shared Celery task dispatch, lifecycle logging, and status serialization."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from celery import current_task
from celery.result import AsyncResult
from celery.signals import task_failure, task_postrun, task_prerun, task_retry
from django.core.cache import cache


logger = logging.getLogger("core.task_lifecycle")

TASK_DEDUPE_PREFIX = "celery_task_dedupe:"
TASK_DEDUPE_TTL = 2 * 60 * 60
TASK_CONTEXT_PREFIX = "celery_task_context:"
TASK_CONTEXT_TTL = 60 * 60

CELERY_TO_API_STATUS = {
    "PENDING": "pending",
    "RECEIVED": "pending",
    "STARTED": "processing",
    "PROGRESS": "processing",
    "RETRY": "retrying",
    "SUCCESS": "succeeded",
    "FAILURE": "failed",
    "REVOKED": "cancelled",
}


def canonical_task_status(state: str | None) -> str:
    """Map Celery's state names to the product's stable task states."""
    return CELERY_TO_API_STATUS.get(str(state or "PENDING").upper(), "pending")


def _active_task_headers() -> dict[str, Any]:
    """Read context from a parent Celery task when dispatching a child task."""
    try:
        headers = getattr(getattr(current_task, "request", None), "headers", None)
    except Exception:
        headers = None
    return dict(headers or {})


def _dedupe_cache_key(dedupe_key: str) -> str:
    return f"{TASK_DEDUPE_PREFIX}{dedupe_key}"


def _task_context_cache_key(task_id: str) -> str:
    return f"{TASK_CONTEXT_PREFIX}{task_id}"


def _store_task_context(task_id, task_name, headers):
    context = {
        "task_id": str(task_id),
        "task_name": task_name,
        "request_id": headers.get("request_id"),
        "video_id": headers.get("video_id"),
        "user_id": headers.get("user_id"),
    }
    context = {key: value for key, value in context.items() if value is not None}
    try:
        cache.set(_task_context_cache_key(str(task_id)), context, TASK_CONTEXT_TTL)
    except Exception:
        logger.warning("task context storage failed task_id=%s", task_id, exc_info=True)


def get_task_context(task_id):
    """Return the short-lived ownership context recorded at dispatch time."""
    try:
        context = cache.get(_task_context_cache_key(str(task_id)))
    except Exception:
        logger.warning("task context lookup failed task_id=%s", task_id, exc_info=True)
        return None
    return dict(context) if isinstance(context, dict) else None


def task_context_matches(task_id, *, video_id=None, user_id=None, is_admin=False):
    """Check whether a caller may inspect a task's status."""
    context = get_task_context(task_id)
    if not context:
        return False
    if is_admin:
        return True
    if video_id is not None and str(context.get("video_id")) != str(video_id):
        return False
    if user_id is not None and str(context.get("user_id")) != str(user_id):
        return False
    return True


def _existing_deduplicated_task(task, task_id):
    """Build an AsyncResult for a task reserved by an earlier submission."""
    return AsyncResult(str(task_id), app=getattr(task, "app", None))


def enqueue_task(
    task,
    *args,
    request=None,
    target_video_id=None,
    dedupe_key=None,
    dedupe_ttl=TASK_DEDUPE_TTL,
    **kwargs,
):
    """Dispatch a task with request/video context in Celery headers.

    Headers are metadata only; they are not added to the task's function
    arguments, so existing task signatures remain compatible.
    """
    headers = _active_task_headers()
    request_id = getattr(request, "request_id", None) if request is not None else None
    if request_id:
        headers["request_id"] = request_id
    if target_video_id is not None:
        headers["video_id"] = str(target_video_id)
    user = getattr(request, "user", None) if request is not None else None
    if getattr(user, "is_authenticated", False) is True and getattr(user, "pk", None) is not None:
        headers["user_id"] = str(user.pk)
    if dedupe_key:
        headers["dedupe_key"] = str(dedupe_key)
        cache_key = _dedupe_cache_key(str(dedupe_key))
        task_id = str(uuid4())
        try:
            existing_id = cache.get(cache_key)
            if existing_id:
                return _existing_deduplicated_task(task, existing_id)

            # SETNX reserves the key before publishing, closing the race where
            # two HTTP requests enqueue the same video at the same time.
            reserved = cache.add(cache_key, task_id, dedupe_ttl)
        except Exception:
            logger.warning(
                "task dedupe unavailable; dispatching normally task=%s dedupe_key=%s",
                getattr(task, "name", None),
                dedupe_key,
                exc_info=True,
            )
        else:
            if reserved:
                try:
                    result = task.apply_async(
                        args=args,
                        kwargs=kwargs,
                        headers=headers,
                        task_id=task_id,
                    )
                    _store_task_context(result.id, getattr(task, "name", None), headers)
                    return result
                except Exception:
                    cache.delete(cache_key)
                    raise

            existing_id = cache.get(cache_key)
            if existing_id:
                return _existing_deduplicated_task(task, existing_id)

    result = task.apply_async(args=args, kwargs=kwargs, headers=headers)
    _store_task_context(result.id, getattr(task, "name", None), headers)
    return result


def report_task_progress(task, *, current: int, total: int = 100, message: str = "", target_video_id=None):
    """Publish best-effort progress metadata without breaking the task itself."""
    try:
        request = getattr(task, "request", None)
        headers = dict(getattr(request, "headers", None) or {})
        task.update_state(
            state="PROGRESS",
            meta={
                "current": current,
                "total": total,
                "percent": round((current / total) * 100, 1) if total else 0,
                "message": message,
                "video_id": target_video_id or headers.get("video_id"),
                "request_id": headers.get("request_id"),
            },
        )
    except Exception:
        logger.warning("task progress update failed task_id=%s", getattr(task, "request", None) and task.request.id)


def _context(task_name, task_id, args=None, request=None) -> dict[str, Any]:
    headers = dict(getattr(request, "headers", None) or {})
    video_id = headers.get("video_id")
    if video_id is None and args:
        # Existing video/AI tasks conventionally use video_id as their first arg.
        video_id = args[0] if isinstance(args[0], (int, str)) else None
    return {
        "task_name": task_name,
        "task_id": task_id,
        "request_id": headers.get("request_id"),
        "video_id": video_id,
    }


def _log_lifecycle(event: str, state: str, task_name, task_id, args=None, request=None, **extra):
    payload = _context(task_name, task_id, args=args, request=request)
    payload.update({"event": event, "state": state, **extra})
    logger.info("task_lifecycle %s", json.dumps(payload, ensure_ascii=False, default=str))


def _release_task_dedupe(request):
    headers = dict(getattr(request, "headers", None) or {})
    dedupe_key = headers.get("dedupe_key")
    if dedupe_key:
        try:
            cache.delete(_dedupe_cache_key(str(dedupe_key)))
        except Exception:
            logger.warning("task dedupe cleanup failed dedupe_key=%s", dedupe_key, exc_info=True)


@task_prerun.connect
def log_task_started(sender=None, task_id=None, task=None, args=None, kwargs=None, **_extra):
    _log_lifecycle(
        "started",
        "processing",
        getattr(sender, "name", None),
        task_id,
        args=args,
        request=getattr(task, "request", None),
        retry_count=getattr(getattr(task, "request", None), "retries", 0),
    )


@task_postrun.connect
def log_task_finished(sender=None, task_id=None, task=None, state=None, args=None, **_extra):
    task_state = canonical_task_status(state)
    _log_lifecycle(
        "finished",
        task_state,
        getattr(sender, "name", None),
        task_id,
        args=args,
        request=getattr(task, "request", None),
    )
    if task_state in {"succeeded", "failed", "cancelled"}:
        _release_task_dedupe(getattr(task, "request", None))


@task_failure.connect
def log_task_failed(sender=None, task_id=None, args=None, exception=None, einfo=None, **_extra):
    request = getattr(sender, "request", None)
    _log_lifecycle(
        "failed",
        "failed",
        getattr(sender, "name", None),
        task_id,
        args=args,
        request=request,
        exception_type=type(exception).__name__ if exception else "Exception",
    )
    logger.error(
        "celery task failed task_id=%s exception_type=%s",
        task_id,
        type(exception).__name__ if exception else "Exception",
    )


@task_retry.connect
def log_task_retry(sender=None, request=None, reason=None, einfo=None, **_extra):
    _log_lifecycle(
        "retrying",
        "retrying",
        getattr(sender, "name", None),
        getattr(request, "id", None),
        args=getattr(request, "args", None),
        request=request,
        reason_type=type(reason).__name__ if reason else "Retry",
    )


def serialize_task_result(result: AsyncResult, *, target_video_id=None) -> dict[str, Any]:
    """Return one safe, backwards-aware payload for task status endpoints."""
    celery_state = str(result.state or "PENDING").upper()
    payload: dict[str, Any] = {
        "task_id": result.id,
        "task_name": getattr(result, "name", None),
        "state": celery_state,
        "status": canonical_task_status(celery_state),
        "ready": result.ready(),
    }

    meta = result.info if isinstance(result.info, dict) else {}
    if target_video_id is not None:
        payload["video_id"] = target_video_id
    elif meta.get("video_id") is not None:
        payload["video_id"] = meta["video_id"]
    if meta.get("request_id"):
        payload["request_id"] = meta["request_id"]

    if celery_state in {"STARTED", "PROGRESS"} and meta:
        payload["progress"] = meta
    elif celery_state == "SUCCESS":
        payload["result"] = result.result or {}
    elif celery_state == "FAILURE":
        payload["error"] = {
            "code": "TASK_FAILED",
            "message": "任务执行失败，请查看日志或稍后重试",
        }
    elif celery_state == "RETRY":
        payload["retry_count"] = meta.get("retry_count", 0)

    return payload
