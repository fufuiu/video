from __future__ import annotations

import io
import json

from django.conf import settings

from .base import OCRBlock, OCRProvider, OCRResult, ProviderConfigurationError, ProviderUnavailableError


def _as_dict(value):
    if isinstance(value, dict):
        return value
    to_map = getattr(value, 'to_map', None)
    return to_map() if callable(to_map) else {}


def parse_ocr_response(response):
    payload = _as_dict(response)
    body = _as_dict(payload.get('body') or getattr(response, 'body', None))
    request_id = str(body.get('requestId') or body.get('request_id') or body.get('RequestId') or '')
    raw_data = body.get('data') or body.get('Data') or '{}'
    data = json.loads(raw_data or '{}') if isinstance(raw_data, str) else _as_dict(raw_data)

    blocks = []
    for item in data.get('prism_wordsInfo') or data.get('prism_words_info') or []:
        if not isinstance(item, dict):
            continue
        block_text = str(item.get('word') or item.get('text') or '').strip()
        if not block_text:
            continue
        polygon = [
            [float(point.get('x', 0)), float(point.get('y', 0))]
            for point in item.get('pos') or []
            if isinstance(point, dict)
        ]
        probability = float(item.get('prob') or item.get('confidence') or 0)
        confidence = probability / 100 if probability > 1 else probability
        blocks.append(OCRBlock(text=block_text, confidence=confidence, polygon=polygon))

    if not blocks and str(data.get('content') or '').strip():
        blocks.append(OCRBlock(text=str(data['content']).strip()))
    return OCRResult(blocks=blocks, provider='aliyun-ocr', request_id=request_id)


class AliyunOCRProvider(OCRProvider):
    name = 'aliyun-ocr'

    def __init__(self, client=None, request_factory=None, runtime_factory=None):
        access_key_id = getattr(settings, 'ALIBABA_CLOUD_ACCESS_KEY_ID', '').strip()
        access_key_secret = getattr(settings, 'ALIBABA_CLOUD_ACCESS_KEY_SECRET', '').strip()
        if not access_key_id or not access_key_secret:
            raise ProviderConfigurationError('阿里云 OCR 访问凭据未配置', provider=self.name)

        if client is None:
            try:
                from alibabacloud_ocr_api20210707 import models as ocr_models
                from alibabacloud_ocr_api20210707.client import Client
                from alibabacloud_tea_openapi import models as open_api_models
                from alibabacloud_tea_util import models as util_models
            except ImportError as exc:
                raise ProviderConfigurationError(
                    '缺少阿里云 OCR SDK，请安装云端可选依赖', provider=self.name
                ) from exc

            config = open_api_models.Config(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                security_token=getattr(settings, 'ALIBABA_CLOUD_SECURITY_TOKEN', '').strip() or None,
            )
            config.endpoint = getattr(
                settings, 'ALIYUN_OCR_ENDPOINT', 'ocr-api.cn-hangzhou.aliyuncs.com'
            )
            client = Client(config)
            request_factory = ocr_models.RecognizeGeneralRequest
            runtime_factory = util_models.RuntimeOptions

        self.client = client
        self.request_factory = request_factory
        self.runtime_factory = runtime_factory

    def recognize(self, image_bytes: bytes) -> OCRResult:
        if not image_bytes:
            raise ProviderUnavailableError('OCR 图片内容为空', provider=self.name, retryable=False)
        if len(image_bytes) > int(getattr(settings, 'ALIYUN_OCR_MAX_IMAGE_BYTES', 10 * 1024 * 1024)):
            raise ProviderUnavailableError('OCR 图片超过服务大小限制', provider=self.name, retryable=False)
        try:
            request = self.request_factory(body=io.BytesIO(image_bytes))
            response = self.client.recognize_general_with_options(request, self.runtime_factory())
            return parse_ocr_response(response)
        except (ProviderConfigurationError, ProviderUnavailableError):
            raise
        except Exception as exc:
            error_code = str(getattr(exc, 'code', '') or '')
            if error_code == 'ocrServiceNotOpen':
                raise ProviderConfigurationError(
                    '阿里云 OCR 服务尚未开通，请先在阿里云控制台开通文字识别服务',
                    provider=self.name,
                ) from exc
            if error_code in {'InvalidAccessKeyId.NotFound', 'InvalidAccessKeyId'}:
                raise ProviderConfigurationError(
                    '阿里云 OCR AccessKey 无效或无权访问',
                    provider=self.name,
                ) from exc
            raise ProviderUnavailableError('阿里云 OCR 调用失败', provider=self.name) from exc
