from __future__ import annotations

import json

from django.conf import settings

from .base import (
    ModerationProvider,
    ModerationResult,
    ProviderConfigurationError,
    ProviderJob,
    ProviderUnavailableError,
)


def _as_dict(value):
    if isinstance(value, dict):
        return value
    to_map = getattr(value, 'to_map', None)
    return to_map() if callable(to_map) else {}


def _get(data, *names, default=None):
    if not isinstance(data, dict):
        return default
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        if name in data:
            return data[name]
        if name.lower() in lowered:
            return lowered[name.lower()]
    return default


def _body(response):
    payload = _as_dict(response)
    return _as_dict(_get(payload, 'body', default=getattr(response, 'body', None)))


def parse_moderation_response(response, *, job_id=''):
    body = _body(response)
    code = int(_get(body, 'code', default=0) or 0)
    request_id = str(_get(body, 'requestId', 'request_id', default='') or '')
    if code == 280:
        return ProviderJob(
            provider='aliyun-moderation', job_id=str(job_id), status='processing', request_id=request_id
        )
    if code != 200:
        raise ProviderUnavailableError('阿里云视频审核查询失败', provider='aliyun-moderation')

    data = _as_dict(_get(body, 'data', default={}))
    risk_level = str(_get(data, 'riskLevel', 'risk_level', default='none') or 'none').lower()
    frame_result = _as_dict(_get(data, 'frameResult', 'frame_result', default={}))
    labels = []
    max_confidence = 0.0
    for frame in _get(frame_result, 'frames', default=[]) or []:
        frame = _as_dict(frame)
        offset = float(_get(frame, 'offset', default=0) or 0)
        frame_risk = str(_get(frame, 'riskLevel', 'risk_level', default='none') or 'none').lower()
        for service_result in _get(frame, 'results', default=[]) or []:
            service_result = _as_dict(service_result)
            service = str(_get(service_result, 'service', default='') or '')
            for item in _get(service_result, 'result', default=[]) or []:
                item = _as_dict(item)
                label = str(_get(item, 'label', default='') or '')
                if not label or label == 'nonLabel':
                    continue
                confidence = float(_get(item, 'confidence', default=0) or 0)
                confidence = confidence / 100 if confidence > 1 else confidence
                max_confidence = max(max_confidence, confidence)
                labels.append({
                    'name': label,
                    'description': str(_get(item, 'description', default='') or ''),
                    'confidence': confidence,
                    'risk_level': frame_risk,
                    'offset': offset,
                    'service': service,
                })

    decision = {'none': 'safe', 'low': 'review', 'medium': 'review', 'high': 'reject'}.get(
        risk_level, 'review'
    )
    if decision == 'safe':
        max_confidence = max_confidence or 1.0
    return ModerationResult(
        decision=decision,
        provider='aliyun-moderation',
        confidence=max_confidence,
        labels=labels,
        request_id=request_id,
    )


class AliyunVideoModerationProvider(ModerationProvider):
    name = 'aliyun-moderation'

    def __init__(self, client=None, submit_request_factory=None, result_request_factory=None):
        access_key_id = getattr(settings, 'ALIBABA_CLOUD_ACCESS_KEY_ID', '').strip()
        access_key_secret = getattr(settings, 'ALIBABA_CLOUD_ACCESS_KEY_SECRET', '').strip()
        if not access_key_id or not access_key_secret:
            raise ProviderConfigurationError('阿里云视频审核访问凭据未配置', provider=self.name)

        if client is None:
            try:
                from alibabacloud_green20220302 import models
                from alibabacloud_green20220302.client import Client
                from alibabacloud_tea_openapi.models import Config
            except ImportError as exc:
                raise ProviderConfigurationError(
                    '缺少阿里云内容安全 SDK，请安装云端可选依赖', provider=self.name
                ) from exc
            timeout_ms = int(float(getattr(settings, 'AI_PROVIDER_TIMEOUT_SECONDS', 60)) * 1000)
            config = Config(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                security_token=getattr(settings, 'ALIBABA_CLOUD_SECURITY_TOKEN', '').strip() or None,
                connect_timeout=min(timeout_ms, 10_000),
                read_timeout=timeout_ms,
                region_id=getattr(settings, 'ALIYUN_GREEN_REGION', 'cn-shanghai'),
                endpoint=getattr(settings, 'ALIYUN_GREEN_ENDPOINT', 'green-cip.cn-shanghai.aliyuncs.com'),
            )
            client = Client(config)
            submit_request_factory = models.VideoModerationRequest
            result_request_factory = models.VideoModerationResultRequest

        self.client = client
        self.submit_request_factory = submit_request_factory
        self.result_request_factory = result_request_factory
        self.service = getattr(settings, 'ALIYUN_VIDEO_MODERATION_SERVICE', 'videoDetection')

    def submit(self, file_url: str) -> ProviderJob:
        try:
            request = self.submit_request_factory(
                service=self.service,
                service_parameters=json.dumps({'url': file_url}),
            )
            response = self.client.video_moderation(request)
            body = _body(response)
            response_code = str(_get(body, 'code', default='') or '')
            response_message = str(_get(body, 'message', default='') or '')
            if response_code != '200':
                if response_code in {'401', '403', '408'} or 'permission' in response_message.lower():
                    raise ProviderConfigurationError(
                        '阿里云内容安全服务未开通或 RAM 无调用权限',
                        provider=self.name,
                    )
                raise ProviderUnavailableError('阿里云视频审核提交失败', provider=self.name)
            data = _as_dict(_get(body, 'data', default={}))
            job_id = str(_get(data, 'taskId', 'task_id', default='') or '')
            if not job_id:
                raise ProviderUnavailableError('阿里云视频审核未返回任务编号', provider=self.name)
            return ProviderJob(
                provider=self.name,
                job_id=job_id,
                request_id=str(_get(body, 'requestId', 'request_id', default='') or ''),
            )
        except (ProviderConfigurationError, ProviderUnavailableError):
            raise
        except Exception as exc:
            raise ProviderUnavailableError('阿里云视频审核提交失败', provider=self.name) from exc

    def result(self, job_id: str):
        try:
            request = self.result_request_factory(
                service=self.service,
                service_parameters=json.dumps({'taskId': str(job_id)}),
            )
            return parse_moderation_response(self.client.video_moderation_result(request), job_id=job_id)
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError('阿里云视频审核查询失败', provider=self.name) from exc
