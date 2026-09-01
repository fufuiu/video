import asyncio
import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError

from ai_service.providers import ProviderUnavailableError, get_provider
from ai_service.providers.aliyun_asr import AliyunSpeechToTextProvider, parse_transcription_payload
from ai_service.providers.aliyun_ocr import AliyunOCRProvider, parse_ocr_response
from ai_service.providers.aliyun_moderation import (
    AliyunVideoModerationProvider,
    parse_moderation_response,
)
from ai_service.providers.base import ProviderJob
from ai_service.providers.base import ProviderConfigurationError
from ai_service.services.deepseek_service import DeepSeekService
from ai_service.storage import get_temporary_storage
from ai_service.storage.aliyun_oss import build_object_key


class ProviderRegistryTests(SimpleTestCase):
    @override_settings(
        AI_TEXT_PROVIDER='mock',
        AI_ASR_PROVIDER='mock',
        AI_OCR_PROVIDER='mock',
        AI_MODERATION_PROVIDER='mock',
        AI_STORAGE_PROVIDER='local',
    )
    def test_ai_config_check_accepts_mock_stack_without_external_calls(self):
        output = StringIO()

        call_command('check_ai_config', stdout=output)

        self.assertIn('validation passed', output.getvalue())

    @override_settings(
        AI_TEXT_PROVIDER='mock',
        AI_ASR_PROVIDER='mock',
        AI_OCR_PROVIDER='mock',
        AI_MODERATION_PROVIDER='mock',
        AI_STORAGE_PROVIDER='aliyun',
        ALIBABA_CLOUD_ACCESS_KEY_ID='',
        ALIBABA_CLOUD_ACCESS_KEY_SECRET='',
        ALIYUN_OSS_BUCKET='',
    )
    def test_ai_config_check_rejects_incomplete_oss_configuration(self):
        with self.assertRaises(CommandError):
            call_command('check_ai_config', stdout=StringIO(), stderr=StringIO())

    @override_settings(AI_TEXT_PROVIDER='mock')
    def test_mock_text_provider_is_deterministic(self):
        provider = get_provider('text')

        result = asyncio.run(provider.complete([{'role': 'user', 'content': 'hello'}]))

        self.assertEqual(result.provider, 'mock')
        self.assertEqual(result.content, 'Mock AI response')

    @override_settings(AI_ASR_PROVIDER='mock')
    def test_mock_asr_returns_normalized_segments(self):
        provider = get_provider('asr')

        job = provider.submit('https://example.invalid/audio.wav')
        result = provider.result(job.job_id)

        self.assertEqual(job.provider, 'mock')
        self.assertEqual(result.segments[0].text, 'Mock subtitle')

    @override_settings(AI_OCR_PROVIDER='disabled')
    def test_disabled_provider_fails_only_when_invoked(self):
        provider = get_provider('ocr')

        with self.assertRaises(ProviderUnavailableError) as context:
            provider.recognize(b'image')

        self.assertFalse(context.exception.retryable)

    @override_settings(AI_TEXT_PROVIDER='deepseek', DEEPSEEK_API_KEY='')
    def test_deepseek_provider_requires_key_only_when_selected(self):
        with self.assertRaises(ProviderConfigurationError):
            get_provider('text')

    @override_settings(AI_TEXT_PROVIDER='mock')
    def test_legacy_deepseek_service_uses_configured_provider(self):
        service = DeepSeekService()

        result = asyncio.run(service.chat_completion([{'role': 'user', 'content': 'hello'}]))

        self.assertEqual(result['provider'], 'mock')
        self.assertEqual(result['choices'][0]['message']['content'], 'Mock AI response')

    def test_aliyun_asr_payload_is_normalized_to_seconds(self):
        result = parse_transcription_payload({
            'transcripts': [{
                'language': 'zh',
                'content_duration_in_milliseconds': 2500,
                'sentences': [
                    {'begin_time': 500, 'end_time': 1500, 'text': '你好'},
                ],
            }],
        })

        self.assertEqual(result.language, 'zh')
        self.assertEqual(result.duration, 2.5)
        self.assertEqual(result.segments[0].start, 0.5)
        self.assertEqual(result.segments[0].end, 1.5)

    @override_settings(
        DASHSCOPE_API_KEY='test-key',
        DASHSCOPE_BASE_URL='https://workspace.example.invalid',
        DASHSCOPE_ASR_MODEL='fun-asr',
    )
    def test_aliyun_asr_does_not_send_bearer_token_to_result_url(self):
        client = MagicMock()
        task_response = MagicMock()
        task_response.json.return_value = {
            'request_id': 'req-asr',
            'output': {
                'task_status': 'SUCCEEDED',
                'results': [{'transcription_url': 'https://signed.example.invalid/result.json'}],
            },
        }
        transcript_response = MagicMock()
        transcript_response.json.return_value = {'transcripts': []}
        client.get.side_effect = [task_response, transcript_response]
        provider = AliyunSpeechToTextProvider(client=client)

        provider.result('job-1')

        second_call = client.get.call_args_list[1]
        self.assertEqual(second_call.args[0], 'https://signed.example.invalid/result.json')
        self.assertNotIn('headers', second_call.kwargs)

    def test_aliyun_ocr_response_is_normalized(self):
        result = parse_ocr_response({
            'body': {
                'RequestId': 'req-ocr',
                'Data': '{"prism_wordsInfo":[{"word":"subtitle","prob":98,'
                        '"pos":[{"x":1,"y":2},{"x":3,"y":4}]}]}',
            },
        })

        self.assertEqual(result.provider, 'aliyun-ocr')
        self.assertEqual(result.request_id, 'req-ocr')
        self.assertEqual(result.blocks[0].text, 'subtitle')
        self.assertEqual(result.blocks[0].confidence, 0.98)
        self.assertEqual(result.blocks[0].polygon[0], [1.0, 2.0])

    @override_settings(
        ALIBABA_CLOUD_ACCESS_KEY_ID='test-id',
        ALIBABA_CLOUD_ACCESS_KEY_SECRET='test-secret',
    )
    def test_aliyun_ocr_sends_image_as_binary_stream(self):
        client = MagicMock()
        client.recognize_general_with_options.return_value = {'body': {'Data': '{}'}}
        request_factory = MagicMock(return_value='request')
        runtime_factory = MagicMock(return_value='runtime')
        provider = AliyunOCRProvider(
            client=client,
            request_factory=request_factory,
            runtime_factory=runtime_factory,
        )

        provider.recognize(b'image-bytes')

        request_factory.assert_called_once()
        self.assertEqual(request_factory.call_args.kwargs['body'].read(), b'image-bytes')
        client.recognize_general_with_options.assert_called_once_with('request', 'runtime')

    @override_settings(
        ALIBABA_CLOUD_ACCESS_KEY_ID='test-id',
        ALIBABA_CLOUD_ACCESS_KEY_SECRET='test-secret',
    )
    def test_aliyun_ocr_reports_service_not_open_as_configuration_error(self):
        client = MagicMock()
        provider_error = RuntimeError('remote request failed')
        provider_error.code = 'ocrServiceNotOpen'
        client.recognize_general_with_options.side_effect = provider_error
        provider = AliyunOCRProvider(
            client=client,
            request_factory=MagicMock(return_value='request'),
            runtime_factory=MagicMock(return_value='runtime'),
        )

        with self.assertRaises(ProviderConfigurationError) as context:
            provider.recognize(b'image-bytes')

        self.assertEqual(context.exception.code, 'AI_PROVIDER_NOT_CONFIGURED')
        self.assertIn('OCR 服务尚未开通', context.exception.safe_message)

    def test_aliyun_moderation_response_is_normalized(self):
        result = parse_moderation_response({
            'body': {
                'Code': 200,
                'RequestId': 'req-green',
                'Data': {
                    'RiskLevel': 'high',
                    'FrameResult': {
                        'Frames': [{
                            'Offset': 12,
                            'RiskLevel': 'high',
                            'Results': [{
                                'Service': 'baselineCheck',
                                'Result': [{'Label': 'violent_explosion', 'Confidence': 74.1}],
                            }],
                        }],
                    },
                },
            },
        }, job_id='job-green')

        self.assertEqual(result.decision, 'reject')
        self.assertEqual(result.confidence, 0.741)
        self.assertEqual(result.labels[0]['offset'], 12.0)
        self.assertEqual(result.request_id, 'req-green')

    def test_aliyun_moderation_processing_response_remains_a_job(self):
        result = parse_moderation_response(
            {'body': {'Code': 280, 'RequestId': 'req-pending'}}, job_id='job-green'
        )

        self.assertIsInstance(result, ProviderJob)
        self.assertEqual(result.status, 'processing')

    @override_settings(
        ALIBABA_CLOUD_ACCESS_KEY_ID='test-id',
        ALIBABA_CLOUD_ACCESS_KEY_SECRET='test-secret',
        ALIYUN_VIDEO_MODERATION_SERVICE='videoDetection',
    )
    def test_aliyun_moderation_submits_signed_url(self):
        client = MagicMock()
        client.video_moderation.return_value = {
            'body': {'Code': 200, 'RequestId': 'req-submit', 'Data': {'TaskId': 'job-green'}}
        }
        request_factory = MagicMock(return_value='request')
        provider = AliyunVideoModerationProvider(
            client=client,
            submit_request_factory=request_factory,
            result_request_factory=MagicMock(),
        )

        job = provider.submit('https://signed.example.invalid/video.mp4')

        self.assertEqual(job.job_id, 'job-green')
        parameters = json.loads(request_factory.call_args.kwargs['service_parameters'])
        self.assertEqual(parameters, {'url': 'https://signed.example.invalid/video.mp4'})

    @override_settings(
        ALIBABA_CLOUD_ACCESS_KEY_ID='test-id',
        ALIBABA_CLOUD_ACCESS_KEY_SECRET='test-secret',
        ALIYUN_VIDEO_MODERATION_SERVICE='videoDetection',
    )
    def test_aliyun_moderation_reports_missing_permission_as_configuration_error(self):
        client = MagicMock()
        client.video_moderation.return_value = {
            'body': {'Code': 408, 'Message': 'No permissions.', 'RequestId': 'req-denied'}
        }
        provider = AliyunVideoModerationProvider(
            client=client,
            submit_request_factory=MagicMock(return_value='request'),
            result_request_factory=MagicMock(),
        )

        with self.assertRaises(ProviderConfigurationError) as context:
            provider.submit('https://signed.example.invalid/video.mp4')

        self.assertFalse(context.exception.retryable)
        self.assertIn('RAM', context.exception.safe_message)

    def test_oss_object_keys_do_not_include_user_filenames(self):
        key = build_object_key('敏感 文件名.mp4', purpose='subtitle/asr', prefix='/ai-temp/')

        self.assertTrue(key.startswith('ai-temp/subtitle-asr/'))
        self.assertTrue(key.endswith('.mp4'))
        self.assertNotIn('敏感', key)

    @override_settings(AI_STORAGE_PROVIDER='local')
    def test_local_storage_never_deletes_application_media(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'video.mp4'
            path.write_bytes(b'video')
            storage = get_temporary_storage()

            stored = storage.upload_file(path)
            storage.delete(stored.key)

            self.assertTrue(path.exists())
            with self.assertRaises(ProviderConfigurationError):
                storage.signed_download_url(stored.key)

    @override_settings(AI_STORAGE_PROVIDER='aliyun')
    def test_aliyun_storage_alias_is_registered(self):
        storage = get_temporary_storage()

        self.assertEqual(storage.__class__.__name__, 'AliyunOSSTemporaryStorage')

# Create your tests here.
