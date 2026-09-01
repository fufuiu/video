"""
AI 服务层
提供各种 AI 功能的封装服务
"""
__all__ = [
    'WhisperService',
    'OCRService',
    'NSFWDetector',
]


def __getattr__(name):
    """按需加载 AI 服务，避免 Django 启动时导入模型依赖。"""
    if name == 'WhisperService':
        from .whisper_service import WhisperService
        return WhisperService
    if name == 'OCRService':
        from .ocr_service import OCRService
        return OCRService
    if name == 'NSFWDetector':
        from .nsfw_service import NSFWDetector
        return NSFWDetector
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
