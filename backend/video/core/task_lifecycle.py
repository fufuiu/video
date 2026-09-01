"""Shared Celery task dispatch, lifecycle logging, and status serialization."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from celery import current_app, current_task
from celery.result import AsyncResult
from celery.signals import task_failure, task_postrun, task_prerun, task_retry
from django.core.cache import cache
from django.utils import timezone


logger = logging.getLogger("core.task_lifecycle")

TASK_DEDUPE_PREFIX = "celery_task_dedupe:"
TASK_DEDUPE_TTL = 2 * 60 * 60
TASK_CONTEXT_PREFIX = "celery_task_context:"
TASK_CONTEXT_TTL = 60 * 60
RETRYABLE_TASK_NAMES = {
    "videos.tasks.process_video",
    "ai_service.tasks.generate_video_subtitles",
    "ai_service.tasks.detect_video_subtitle",
    "ai_service.tasks.moderate_video_task",
    "ai_service.tasks.summarize_video_task",
}

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


def _json_safe(value):
    """Return JSON-compatible task parameters without serializing objects."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower() for part in ("password", "secret", "token", "api_key", "authorization")):
                safe[key_text] = "[redacted]"
            else:
                safe[key_text] = _json_safe(item)
        return safe
    return str(value)


def _persist_task_context(task_id, task_name, headers, args=None, kwargs=None):
    """Persist dispatch metadata without making queue publishing depend on MySQL."""
    try:
        from core.models import TaskExecution

        retry_of_id = headers.get("retry_of_task_id")
        retry_of = None
        if retry_of_id:
            retry_of = TaskExecution.objects.filter(task_id=str(retry_of_id)).first()

        retryable = task_name in RETRYABLE_TASK_NAMES
        parameters = {}
        if retryable:
            parameters = {
                "args": _json_safe(list(args or ())),
                "kwargs": _json_safe(dict(kwargs or {})),
            }

        TaskExecution.objects.update_or_create(
            task_id=str(task_id),
            defaults={
                "task_name": task_name or "unknown",
                "request_id": str(headers.get("request_id") or ""),
                "video_id": headers.get("video_id"),
                "user_id": headers.get("user_id"),
                "retry_of": retry_of,
                "status": "pending",
                "celery_state": "PENDING",
                "parameters": parameters,
                "retryable": retryable,
            },
        )
    except Exception:
        logger.warning("persistent task context storage failed task_id=%s", task_id, exc_info=True)


def _store_task_context(task_id, task_name, headers, args=None, kwargs=None):
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
    _persist_task_context(task_id, task_name, headers, args=args, kwargs=kwargs)


def get_task_context(task_id):
    """Return ownership context from cache, falling back to task history."""
    try:
        context = cache.get(_task_context_cache_key(str(task_id)))
    except Exception:
        logger.warning("task context lookup failed task_id=%s", task_id, exc_info=True)
        context = None
    if isinstance(context, dict):
        return dict(context)

    try:
        from core.models import TaskExecution

        stored = TaskExecution.objects.filter(task_id=str(task_id)).values(
            "task_id", "task_name", "request_id", "video_id", "user_id"
        ).first()
    except Exception:
        logger.warning("persistent task context lookup failed task_id=%s", task_id, exc_info=True)
        return None
    if not stored:
        return None
    return {key: str(value) if key.endswith("_id") and value is not None else value for key, value in stored.items()}


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
    target_user_id=None,
    dedupe_key=None,
    dedupe_ttl=TASK_DEDUPE_TTL,
    retry_of=None,
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
    if target_user_id is not None:
        headers["user_id"] = str(target_user_id)
    if retry_of is not None:
        headers["retry_of_task_id"] = str(retry_of)
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
                    _store_task_context(
                        result.id,
                        getattr(task, "name", None),
                        headers,
                        args=args,
                        kwargs=kwargs,
                    )
                    return result
                except Exception:
                    cache.delete(cache_key)
                    raise

            existing_id = cache.get(cache_key)
            if existing_id:
                return _existing_deduplicated_task(task, existing_id)

    result = task.apply_async(args=args, kwargs=kwargs, headers=headers)
    _store_task_context(
        result.id,
        getattr(task, "name", None),
        headers,
        args=args,
        kwargs=kwargs,
    )
    return result


def report_task_progress(
    task,
    *,
    current: int,
    total: int = 100,
    message: str = "",
    target_video_id=None,
    metadata=None,
):
    """Publish best-effort progress metadata without breaking the task itself."""
    try:
        request = getattr(task, "request", None)
        headers = dict(getattr(request, "headers", None) or {})
        progress = {
            "current": current,
            "total": total,
            "percent": round((current / total) * 100, 1) if total else 0,
            "message": message,
            "video_id": target_video_id or headers.get("video_id"),
            "request_id": headers.get("request_id"),
        }
        if metadata:
            progress.update(_json_safe(metadata))
        task.update_state(
            state="PROGRESS",
            meta=progress,
        )
        _persist_task_state(
            getattr(request, "id", None),
            "PROGRESS",
            task_name=getattr(task, "name", None),
            request=request,
            progress=progress,
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


def _persist_task_state(
    task_id,
    celery_state,
    *,
    task_name=None,
    args=None,
    request=None,
    progress=None,
    error_code=None,
    error_message=None,
):
    """Best-effort state persistence; task execution must survive DB outages."""
    if not task_id:
        return
    try:
        from core.models import TaskExecution

        state = str(celery_state or "PENDING").upper()
        status = canonical_task_status(state)
        headers = dict(getattr(request, "headers", None) or {})
        context = _context(task_name, task_id, args=args, request=request)
        defaults = {
            "task_name": task_name or context.get("task_name") or "unknown",
            "request_id": str(context.get("request_id") or ""),
            "video_id": context.get("video_id"),
            "user_id": headers.get("user_id"),
            "status": status,
            "celery_state": state,
            "retry_count": int(getattr(request, "retries", 0) or 0),
            "retryable": (task_name or context.get("task_name")) in RETRYABLE_TASK_NAMES,
        }
        record, _created = TaskExecution.objects.get_or_create(task_id=str(task_id), defaults=defaults)
        updates = {
            "status": status,
            "celery_state": state,
            "retry_count": int(getattr(request, "retries", 0) or 0),
        }
        now = timezone.now()
        if state in {"STARTED", "PROGRESS"} and record.started_at is None:
            updates["started_at"] = now
        if progress is not None:
            updates["progress"] = _json_safe(progress)
        if status in {"succeeded", "failed", "cancelled"}:
            updates["finished_at"] = now
        if status == "failed":
            if error_code and error_message:
                updates.update({
                    "error_code": str(error_code)[:100],
                    "error_message": str(error_message)[:500],
                })
            elif not record.error_code or not record.error_message:
                updates.update({
                    "error_code": "TASK_FAILED",
                    "error_message": "任务执行失败，请查看日志或稍后重试",
                })
        TaskExecution.objects.filter(pk=record.pk).update(**updates)
    except Exception:
        logger.warning("persistent task state update failed task_id=%s", task_id, exc_info=True)


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
    _persist_task_state(
        task_id,
        "STARTED",
        task_name=getattr(sender, "name", None),
        args=args,
        request=getattr(task, "request", None),
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
    _persist_task_state(
        task_id,
        state,
        task_name=getattr(sender, "name", None),
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
    _persist_task_state(
        task_id,
        "FAILURE",
        task_name=getattr(sender, "name", None),
        args=args,
        request=request,
        error_code=getattr(exception, "code", None),
        error_message=getattr(exception, "safe_message", None),
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
    _persist_task_state(
        getattr(request, "id", None),
        "RETRY",
        task_name=getattr(sender, "name", None),
        args=getattr(request, "args", None),
        request=request,
    )


def retry_task_execution(execution, *, request=None):
    """Safely re-dispatch one failed, explicitly allow-listed task."""
    from core.models import TaskExecution

    if execution.task_name not in RETRYABLE_TASK_NAMES:
        raise ValueError("该任务类型不允许重试")
    if not execution.can_retry:
        raise ValueError("当前任务状态不允许重试或已提交重试")

    claimed = TaskExecution.objects.filter(
        pk=execution.pk,
        status__in=TaskExecution.RETRYABLE_STATUSES,
        retryable=True,
        retry_dispatched_at__isnull=True,
    ).update(retry_dispatched_at=timezone.now())
    if claimed != 1:
        raise ValueError("当前任务已被其他请求重试")

    task = current_app.tasks.get(execution.task_name)
    if task is None:
        TaskExecution.objects.filter(pk=execution.pk).update(retry_dispatched_at=None)
        raise ValueError("任务处理器当前不可用")

    parameters = execution.parameters or {}
    args = parameters.get("args") or []
    kwargs = parameters.get("kwargs") or {}
    try:
        return enqueue_task(
            task,
            *args,
            request=request,
            target_video_id=execution.video_id,
            target_user_id=execution.user_id,
            retry_of=execution.task_id,
            **kwargs,
        )
    except Exception:
        TaskExecution.objects.filter(pk=execution.pk).update(retry_dispatched_at=None)
        raise


def serialize_task_result(result: AsyncResult, *, target_video_id=None) -> dict[str, Any]:
    """Return one safe, backwards-aware payload for task status endpoints."""
    celery_state = str(result.state or "PENDING").upper()
    stored = None
    try:
        from core.models import TaskExecution

        stored = TaskExecution.objects.filter(task_id=str(result.id)).first()
    except Exception:
        logger.warning("persistent task status lookup failed task_id=%s", result.id, exc_info=True)
    if celery_state == "PENDING" and stored and stored.celery_state != "PENDING":
        celery_state = stored.celery_state
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

    if stored:
        payload["task_name"] = stored.task_name
        payload["status"] = stored.status
        if stored.request_id:
            payload["request_id"] = stored.request_id
        if stored.video_id is not None:
            payload["video_id"] = stored.video_id
        if stored.progress and "progress" not in payload:
            payload["progress"] = stored.progress
        if stored.status == "failed" and stored.error_code and stored.error_message:
            payload["error"] = {
                "code": stored.error_code,
                "message": stored.error_message,
            }
        payload["can_retry"] = stored.can_retry

    return payload
