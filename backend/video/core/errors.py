"""统一 API 错误响应。

业务视图在迁移期间仍可能返回 ``detail``、``error`` 或字段错误字典。
这里将异常和这些旧格式统一为稳定的错误信封，避免把内部异常细节暴露给客户端。
"""

from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


ERROR_CODES = {
    400: "VALIDATION_ERROR",
    401: "AUTHENTICATION_REQUIRED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    409: "CONFLICT",
    429: "RATE_LIMITED",
}

DEFAULT_MESSAGES = {
    400: "请求参数无效",
    401: "请先登录",
    403: "没有权限执行此操作",
    404: "请求的资源不存在",
    405: "不支持此请求方法",
    408: "请求超时，请稍后重试",
    409: "请求与当前资源状态冲突",
    429: "请求过于频繁，请稍后重试",
}


def error_code_for_status(status_code: int) -> str:
    if status_code in ERROR_CODES:
        return ERROR_CODES[status_code]
    if status_code >= 500:
        return "INTERNAL_SERVER_ERROR"
    return "REQUEST_FAILED"


def default_message_for_status(status_code: int) -> str:
    if status_code in DEFAULT_MESSAGES:
        return DEFAULT_MESSAGES[status_code]
    if status_code >= 500:
        return "服务器暂时无法处理请求"
    return "请求失败"


def _extract_error(data: Any, status_code: int) -> tuple[str, dict[str, Any], str]:
    """从 DRF 或历史接口响应中提取 message、fields 和 code。"""
    code = error_code_for_status(status_code)
    message = default_message_for_status(status_code)
    fields: dict[str, Any] = {}

    if isinstance(data, dict):
        nested = data.get("error")
        if isinstance(nested, dict):
            code = nested.get("code") or code
            message = nested.get("message") or message
            nested_fields = nested.get("fields")
            if isinstance(nested_fields, dict):
                fields = nested_fields
            return message, fields, code

        if isinstance(nested, str) and status_code < 500:
            message = nested
        elif isinstance(data.get("message"), str) and status_code < 500:
            message = data["message"]
        elif isinstance(data.get("detail"), str) and status_code < 500:
            message = data["detail"]

        if isinstance(data.get("detail"), dict):
            fields = data["detail"]
        elif isinstance(data.get("detail"), list):
            fields = {"non_field_errors": data["detail"]}
        elif isinstance(data.get("fields"), dict):
            fields = data["fields"]
        elif not any(key in data for key in ("detail", "error", "message", "success")):
            fields = data
    elif isinstance(data, list):
        fields = {"non_field_errors": data}

    # 5xx 只返回固定提示，避免把异常、路径、SQL 或依赖信息传给客户端。
    if status_code >= 500:
        message = default_message_for_status(status_code)

    return message, fields, code


def build_error_payload(data: Any, status_code: int, request_id: str | None = None) -> dict[str, Any]:
    message, fields, code = _extract_error(data, status_code)
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "fields": fields,
            "request_id": request_id,
        },
    }


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF 全局异常处理器，统一未处理异常和框架异常。"""
    response = drf_exception_handler(exc, context)
    request = context.get("request")
    request_id = getattr(request, "request_id", None)

    if response is None:
        response = Response(
            build_error_payload(None, status.HTTP_500_INTERNAL_SERVER_ERROR, request_id),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    else:
        response.data = build_error_payload(response.data, response.status_code, request_id)

    if request_id:
        response["X-Request-ID"] = request_id
    return response


class APIErrorResponseMiddleware:
    """统一处理视图手写的错误 Response，兼容迁移期间的旧接口。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return self.process_response(request, response)

    def process_response(self, request, response):
        # 运维探针有自己的机器可读结构，保留其 503 响应内容。
        if (
            request.path.startswith("/api/")
            and not request.path.startswith("/api/health/")
            and response.status_code >= 400
            and hasattr(response, "data")
        ):
            response.data = build_error_payload(
                response.data,
                response.status_code,
                getattr(request, "request_id", None),
            )
            if hasattr(response, "accepted_renderer") and response.accepted_renderer:
                response.content = response.rendered_content

        request_id = getattr(request, "request_id", None)
        if request_id:
            response["X-Request-ID"] = request_id
        return response
