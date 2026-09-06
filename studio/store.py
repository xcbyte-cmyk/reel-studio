from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
EXPORTS = ROOT / 'exports'
for folder in (DATA, EXPORTS, DATA / 'assets'):
    folder.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()
DEFAULTS = {
    'openai_api_key': '', 'openai_model': 'gpt-4.1-mini',
    'tts_provider': 'windows', 'openai_tts_model': 'gpt-4o-mini-tts', 'openai_voice': 'coral',
    'instagram_token': '', 'instagram_user_id': '', 'instagram_login': 'instagram',
    'instagram_api_version': 'v23.0', 'public_base_url': '', 'share_to_feed': True,
}


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    conn = sqlite3.connect(DATA / 'studio.sqlite', timeout=30)
    conn.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id))')
    return conn


@contextmanager
def connection():
    conn = connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def save(kind, record):
    with LOCK, connection() as conn:
        conn.execute('INSERT OR REPLACE INTO records VALUES (?,?,?)',
                     (kind, record['id'], json.dumps(record, ensure_ascii=False)))
    return record


def get(kind, record_id):
    with LOCK, connection() as conn:
        row = conn.execute('SELECT body FROM records WHERE kind=? AND id=?', (kind, record_id)).fetchone()
    if not row:
        raise ValueError('요청한 항목이 없습니다.')
    return json.loads(row[0])


def all_records(kind):
    with LOCK, connection() as conn:
        rows = conn.execute('SELECT body FROM records WHERE kind=? ORDER BY rowid DESC', (kind,)).fetchall()
    return [json.loads(row[0]) for row in rows]


def update(kind, record_id, values):
    with LOCK:
        record = get(kind, record_id)
        record.update(values)
        record['updated_at'] = now()
        return save(kind, record)


def event(job_id, message, **values):
    with LOCK:
        job = get('jobs', job_id)
        if message != job.get('message'):
            job.setdefault('events', []).append({'at': now(), 'message': message})
        job['events'] = job['events'][-100:]
        job.update(message=message, updated_at=now(), **values)
        return save('jobs', job)


def settings(public=False):
    path = DATA / 'settings.json'
    saved = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    config = dict(DEFAULTS, **saved)
    for key, env in [('openai_api_key','OPENAI_API_KEY'), ('instagram_token','INSTAGRAM_ACCESS_TOKEN'),
                     ('instagram_user_id','INSTAGRAM_USER_ID')]:
        config[key] = config.get(key) or os.environ.get(env, '')
    if public:
        config['openai_configured'] = bool(config.pop('openai_api_key'))
        config['instagram_configured'] = bool(config.pop('instagram_token') and config.get('instagram_user_id'))
    return config


def save_settings(values):
    with LOCK:
        config = settings()
        for key in DEFAULTS:
            if key in values and (key not in ('openai_api_key','instagram_token') or values[key]):
                config[key] = values[key]
        if values.get('clear_openai'):
            config['openai_api_key'] = ''
        if values.get('clear_instagram'):
            config['instagram_token'] = ''
        path = DATA / 'settings.json'
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)
    return settings(public=True)


def new_job(values):
    mode, delivery = values.get('mode', 'knowledge'), values.get('delivery', 'export')
    if mode not in ('knowledge','product','highlights'):
        raise ValueError('콘텐츠 모드를 선택해 주세요.')
    if delivery not in ('export','approval','auto'):
        raise ValueError('게시 방식을 선택해 주세요.')
    topic = str(values.get('topic') or values.get('title') or '').strip()
    if not topic:
        raise ValueError('콘텐츠 주제 또는 제목을 입력해 주세요.')
    job = {
        'id': uuid.uuid4().hex[:12], 'title': topic[:100], 'topic': topic,
        'mode': mode, 'delivery': delivery, 'status': 'draft', 'progress': 0,
        'message': '제작 준비 완료', 'created_at': now(), 'updated_at': now(),
        'scheduled_at': None, 'auto_publish': delivery == 'auto', 'tone': '명확하고 친근하게',
        'audience': '일반 시청자', 'brand': 'REEL STUDIO', 'cta': '저장하고 다음 영상에서 만나요.',
        'duration': 30, 'assets': [], 'source_notes': '', 'clip_start': None, 'clip_end': None,
        'script': None, 'artifacts': {}, 'events': [], 'error': None, 'publish_state': {},
    }
    fields = ['title','scheduled_at','tone','audience','brand','cta','duration','assets',
              'source_notes','clip_start','clip_end','script','automation_id']
    for field in fields:
        if field in values:
            job[field] = values[field]
    job['duration'] = max(5, min(180, float(job['duration'] or 30)))
    return save('jobs', job)


def public_job(job):
    result = dict(job)
    result.pop('artifact_paths', None)
    result['assets'] = [{k:v for k,v in a.items() if k != 'path'} for a in result.get('assets', [])]
    # Container and media identifiers are useful when resuming a publication.
    state = result.get('publish_state', {})
    result['publish_state'] = {k:v for k,v in state.items() if k not in ('upload_uri','upload_url','access_token')}
    return result
