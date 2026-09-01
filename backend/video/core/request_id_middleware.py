"""为 HTTP 请求生成可追踪的 request ID。"""

import re
import uuid

from django.utils.deprecation import MiddlewareMixin


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


class RequestIDMiddleware(MiddlewareMixin):
    """复用可信格式的请求 ID，否则生成新的 UUID。"""

    def process_request(self, request):
        candidate = request.META.get("HTTP_X_REQUEST_ID", "").strip()
        request.request_id = candidate if _REQUEST_ID_RE.fullmatch(candidate) else f"req_{uuid.uuid4().hex}"
        return None

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", None)
        if request_id:
            response["X-Request-ID"] = request_id
        return response
