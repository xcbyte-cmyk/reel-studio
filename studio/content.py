from __future__ import annotations

import json
import re
from pathlib import Path

import requests


SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'title': {'type': 'string'}, 'hook': {'type': 'string'},
        'scenes': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'text': {'type':'string'}, 'narration': {'type':'string'}, 'duration': {'type':'number'}},
            'required': ['text','narration','duration'],
        }},
        'caption': {'type':'string'}, 'hashtags': {'type':'array','items':{'type':'string'}},
    }, 'required': ['title','hook','scenes','caption','hashtags'],
}


def normalize_script(script):
    if not isinstance(script, dict) or not isinstance(script.get('scenes'), list) or not script['scenes']:
        raise ValueError('대본에는 하나 이상의 장면이 필요합니다.')
    result = {key: script.get(key, '') for key in ('title','hook','caption')}
    result['scenes'] = []
    for scene in script['scenes'][:30]:
        text = str(scene.get('text') or '').strip()
        narration = str(scene.get('narration') or text).strip()
        if not text:
            raise ValueError('빈 장면 문구를 입력할 수 없습니다.')
        result['scenes'].append({'text':text, 'narration':narration,
                                 'duration':max(1, min(60, float(scene.get('duration') or 5)))})
    tags = script.get('hashtags') or []
    if isinstance(tags, str):
        tags = re.split(r'[\s,]+', tags)
    result['hashtags'] = [('#'+str(t).strip().lstrip('#').replace(' ','')) for t in tags if str(t).strip()][:5]
    if len(result['caption']) + sum(map(len, result['hashtags'])) > 2100:
        result['caption'] = result['caption'][:1900]
    for field in ('provider','notice'):
        if field in script:
            result[field] = script[field]
    return result


def template_script(job):
    topic = job['topic']
    notes = [line.strip(' -•\t') for line in re.split(r'\n+', job.get('source_notes') or '') if line.strip()]
    cta = job.get('cta') or '저장하고 다음 영상에서 만나요.'
    if job['mode'] == 'highlights':
        lines = [topic]
        notice = '원본 영상의 지정 구간을 사용합니다. 음성 인식 연결 전에는 원본 대사 자막을 생성하지 않습니다.'
    elif job['mode'] == 'product':
        lines = [f'{topic}, 이렇게 활용해 보세요.'] + (notes[:4] or [
            '제품의 실제 사용 장면을 보여주세요.',
            '가장 알리고 싶은 특징을 한 문장으로 소개하세요.',
            '구체적인 사용 방법과 구매 정보를 입력하세요.',
        ]) + [cta]
        notice = '입력 자료를 배치한 템플릿 초안입니다. 제품 특징·가격은 제공된 내용만 사용합니다.'
    else:
        lines = [f'{topic}, 핵심부터 정리해 볼까요?'] + (notes[:4] or [
            '먼저, 설명할 핵심 개념을 한 문장으로 정리하세요.',
            '다음으로, 실제 사례 하나를 덧붙이세요.',
            '마지막으로, 시청자가 바로 해볼 행동을 제안하세요.',
        ]) + [cta]
        notice = '입력 자료를 배치한 템플릿 초안입니다. API 키를 연결하면 주제에 맞는 AI 대본을 생성합니다.'
    duration = float(job.get('duration') or 30) / len(lines)
    script = {
        'title': topic[:70], 'hook': lines[0],
        'scenes': [{'text': (re.split(r'(?<=[.!?])\s+',line)[0]), 'narration':line, 'duration':round(duration, 2)} for line in lines],
        'caption': '\n\n'.join([topic, *notes[:4], cta]),
        'hashtags': ['#릴스', '#'+('제품소개' if job['mode'] == 'product' else '콘텐츠')],
        'provider': 'template', 'notice': notice,
    }
    return normalize_script(script)


def generate_script(job, settings, progress=None):
    if not settings.get('openai_api_key'):
        return template_script(job)
    if progress:
        progress(12, '주제와 참고 자료로 AI 대본을 작성하고 있습니다.')
    source = {k:job.get(k) for k in ['topic','mode','tone','audience','brand','cta','duration','source_notes']}
    if job.get('transcript_segments'):
        begin, end = float(job.get('clip_start') or 0), float(job.get('clip_end') or 999999)
        source['transcript'] = ' '.join(s['text'] for s in job['transcript_segments'] if s['end'] > begin and s['start'] < end)
    instruction = (
        '당신은 한국어 Instagram 릴스 작가입니다. 입력된 주제와 자료를 바탕으로 촬영/편집 가능한 대본을 만드세요. '
        '한국어 구어체, 첫 장면은 구체적인 훅, 중간 3~5장면, 마지막은 CTA. '
        '각 text는 화면용 핵심 문구 45자 이내, narration은 자연스러운 실제 대사. '
        '한 장면 대사는 1~2문장, 전체 내레이션 글자 수는 요청 초수의 4~5배. 장면 duration 합계는 요청 초수. '
        'caption은 게시용 본문, hashtags는 관련 태그 최대 5개. '
        '자료 없는 가격·제품성능·통계·인용·최신 뉴스는 창작하지 말고 자료가 없으면 일반적인 설명과 실제 가능한 행동을 사용하세요. '
        'product는 제공된 제품 설명에 충실하세요. highlights는 제공된 transcript에서 실제 발언 요약과 게시 문구만 만드세요. '
        '반드시 주어진 JSON 형식을 따르세요.'
    )
    response = requests.post('https://api.openai.com/v1/responses',
        headers={'Authorization': 'Bearer '+settings['openai_api_key']},
        json={'model':settings.get('openai_model') or 'gpt-4.1-mini', 'store':False,
              'instructions':instruction, 'input':json.dumps(source, ensure_ascii=False),
              'text':{'format':{'type':'json_schema','name':'reel_script','strict':True,'schema':SCHEMA}}},
        timeout=(15, 180))
    if not response.ok:
        try:
            detail = response.json().get('error',{}).get('message',str(response.status_code))
        except ValueError:
            detail = str(response.status_code)
        raise RuntimeError('AI 대본 생성 실패: '+detail)
    payload = response.json()
    text = ''.join(part.get('text','') for item in payload.get('output',[]) for part in item.get('content',[]) if part.get('type') == 'output_text')
    if not text:
        raise RuntimeError('AI에서 완성된 대본을 받지 못했습니다. 모델 설정과 응답 상태를 확인해 주세요.')
    script = normalize_script(json.loads(text))
    script['provider'] = 'openai'
    script['notice'] = 'AI가 생성한 초안입니다. 장면 문구와 내레이션을 편집할 수 있습니다.'
    return script


def write_script_bundle(script, folder:Path):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'script.json').write_text(json.dumps(script,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'caption.txt').write_text(script['caption']+'\n\n'+' '.join(script['hashtags']),encoding='utf-8')
