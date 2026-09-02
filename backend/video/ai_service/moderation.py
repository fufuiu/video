"""Normalize cloud moderation labels into user-facing review events."""

from __future__ import annotations

from typing import Any


LABEL_NAMES = {
    'political_politicalFigure_name_tii': '疑似出现政治人物姓名',
    'violent_explosion': '疑似出现爆炸或暴力内容',
    'pornographic_adultContent': '疑似出现成人内容',
    'terrorism_terrorist': '疑似出现恐怖主义相关内容',
    'contraband': '疑似出现违禁品',
}

RISK_LEVEL_NAMES = {
    'none': '无风险',
    'low': '低风险提示',
    'medium': '待人工复核',
    'high': '高风险提示',
}


def label_name(label: str, description: str = '') -> str:
    """Return a stable Chinese label while preserving unknown provider labels."""
    label = str(label or '').strip()
    description = str(description or '').strip()
    if label in LABEL_NAMES:
        return LABEL_NAMES[label]
    if description:
        return description
    return f'供应商标签：{label}' if label else '疑似风险内容'


def group_label_events(labels: list[dict[str, Any]], *, max_gap_seconds: float = 2.0):
    """Merge adjacent frames with the same label into reviewable time ranges."""
    normalized = []
    for item in labels or []:
        label = str(item.get('name') or item.get('label') or '').strip()
        if not label:
            continue
        offset = max(0.0, float(item.get('offset', item.get('timestamp', 0)) or 0))
        confidence = max(0.0, min(1.0, float(item.get('confidence', 0) or 0)))
        description = str(item.get('description') or '').strip()
        normalized.append({
            'label': label,
            'label_text': label_name(label, description),
            'description': description,
            'risk_level': str(item.get('risk_level') or '').lower(),
            'service': str(item.get('service') or ''),
            'offset': offset,
            'confidence': confidence,
        })

    normalized.sort(key=lambda item: (item['offset'], item['label'], item['service']))
    events = []
    for item in normalized:
        matching_event = None
        for event in reversed(events):
            same_signal = (
                event['label'] == item['label']
                and event['risk_level'] == item['risk_level']
                and event['service'] == item['service']
            )
            if same_signal and item['offset'] - event['end_time'] <= max_gap_seconds:
                matching_event = event
                break
            if item['offset'] - event['end_time'] > max_gap_seconds:
                break

        if matching_event is None:
            events.append({
                'timestamp': item['offset'],
                'start_time': item['offset'],
                'end_time': item['offset'],
                'label': item['label'],
                'label_text': item['label_text'],
                'description': item['description'],
                'risk_level': item['risk_level'],
                'risk_level_text': RISK_LEVEL_NAMES.get(item['risk_level'], '待人工判断'),
                'confidence': item['confidence'],
                'service': item['service'],
                'source_frame_count': 1,
            })
            continue

        matching_event['end_time'] = item['offset']
        matching_event['source_frame_count'] += 1
        if item['confidence'] > matching_event['confidence']:
            matching_event['confidence'] = item['confidence']
            matching_event['timestamp'] = item['offset']
        if item['description'] and not matching_event['description']:
            matching_event['description'] = item['description']
            matching_event['label_text'] = label_name(item['label'], item['description'])

    for event in events:
        event['reason'] = (
            f"{event['label_text']}（标签匹配置信度 {event['confidence']:.2%}）"
        )
    return events
