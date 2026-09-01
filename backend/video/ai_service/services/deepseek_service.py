"""Compatibility facade for text operations backed by the Provider registry."""

from typing import Dict, List, Optional

from ai_service.providers import get_provider


class DeepSeekService:
    """Preserve existing call sites while routing through TextProvider."""

    def __init__(self):
        self.provider = get_provider('text')
        self.model = getattr(self.provider, 'model', 'configured-provider')

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict:
        if stream:
            raise ValueError('当前文本 Provider 不支持流式响应')
        result = await self.provider.complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return {
            'choices': [{'message': {'content': result.content, 'role': 'assistant'}}],
            'provider': result.provider,
            'model': result.model,
            'request_id': result.request_id,
            'usage': result.usage,
        }

    async def optimize_subtitle(self, subtitle_text: str) -> str:
        result = await self.chat_completion(
            [
                {
                    'role': 'system',
                    'content': '你是一个专业的字幕优化助手。请修正错别字和标点，使字幕通顺易读并保持原意。',
                },
                {'role': 'user', 'content': f'请优化以下字幕文本：\n\n{subtitle_text}'},
            ],
            temperature=0.3,
        )
        return result['choices'][0]['message']['content']

    async def translate_subtitle(self, subtitle_text: str, target_language: str = '英文') -> str:
        result = await self.chat_completion(
            [
                {
                    'role': 'system',
                    'content': f'你是一个专业字幕翻译助手。请翻译成{target_language}并保持时间轴格式不变。',
                },
                {'role': 'user', 'content': f'请翻译以下字幕：\n\n{subtitle_text}'},
            ],
            temperature=0.3,
        )
        return result['choices'][0]['message']['content']

    async def generate_video_summary(self, subtitle_text: str) -> str:
        result = await self.chat_completion(
            [
                {'role': 'system', 'content': '你是视频内容分析助手，请只返回200字以内的中文摘要。'},
                {'role': 'user', 'content': f'请根据以下视频信息生成摘要：\n\n{subtitle_text}'},
            ],
            temperature=0.5,
            max_tokens=500,
        )
        return result['choices'][0]['message']['content']

    async def generate_video_tags(self, title: str, description: str, subtitle_text: str = '') -> List[str]:
        content = f'标题：{title}\n描述：{description}'
        if subtitle_text:
            content += f'\n字幕片段：{subtitle_text[:2000]}'
        result = await self.chat_completion(
            [
                {'role': 'system', 'content': '生成5到10个简短视频标签，只返回逗号分隔的标签。'},
                {'role': 'user', 'content': content},
            ],
            temperature=0.5,
            max_tokens=200,
        )
        raw = result['choices'][0]['message']['content']
        tags = []
        for item in raw.replace('，', ',').replace('\n', ',').split(','):
            tag = item.strip().lstrip('-').strip()
            if tag and tag not in tags:
                tags.append(tag[:30])
        return tags[:10]
