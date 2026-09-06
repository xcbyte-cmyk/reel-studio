from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import store
from .content import generate_script, normalize_script, write_script_bundle

EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix='reel')
ACTIVE = set()
ACTIVE_LOCK = threading.RLock()
BUSY = {'generating','rendering','publishing','queued'}


def parse_time(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone(timedelta(hours=9)))
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise ValueError('예약 시각 형식이 올바르지 않습니다.')


def resolve_assets(assets):
    return [store.get('assets', a['id']) for a in assets]


def edit_job(job_id, values):
    with ACTIVE_LOCK:
        job = store.get('jobs', job_id)
        if job_id in ACTIVE or job['status'] in BUSY:
            raise ValueError('작업이 실행 중입니다. 완료 후 수정해 주세요.')
        if job['status'] in ('published','publishing') or job.get('publish_state'):
            raise ValueError('Instagram에 업로드한 작업은 수정할 수 없습니다. 새 작업을 만들어 주세요.')
        allowed = ['title','topic','mode','delivery','scheduled_at','tone','audience','brand','cta',
                   'duration','source_notes','clip_start','clip_end','script','assets']
        values = dict(values)
        if 'assets' in values:
            values['assets'] = resolve_assets(values['assets'])
        changes = {k:v for k,v in values.items() if k in allowed and v != job.get(k)}
        if not changes:
            return job
        if 'script' in changes and changes['script']:
            changes['script'] = normalize_script(changes['script'])
        if 'assets' in changes:
            changes['assets'] = resolve_assets(changes['assets'])
        if 'mode' in changes and changes['mode'] not in ('knowledge','product','highlights'):
            raise ValueError('콘텐츠 모드를 확인해 주세요.')
        if 'delivery' in changes and changes['delivery'] not in ('export','approval','auto'):
            raise ValueError('게시 방식을 확인해 주세요.')
        if 'scheduled_at' in changes:
            parsed = parse_time(changes['scheduled_at'])
            changes['scheduled_at'] = parsed.isoformat() if parsed else None
        if 'duration' in changes:
            changes['duration'] = max(5,min(180,float(changes['duration'] or 30)))
        content_fields = {'topic','mode','tone','audience','brand','cta','duration','source_notes','clip_start','clip_end','script','assets'}
        if content_fields.intersection(changes):
            changes.update(artifacts={}, artifact_paths={}, status='draft', progress=0, error=None, message='변경 사항을 저장했습니다. 영상을 다시 제작해 주세요.')
            if 'script' not in changes and {'topic','mode','source_notes'}.intersection(changes):
                changes['script'] = None
            if {'assets','clip_start','clip_end'}.intersection(changes):
                changes['transcript_segments'] = []
        elif job['status'] in ('scheduled','approved'):
            changes.update(status='ready',message='게시 설정이 변경되었습니다. 게시 또는 예약을 다시 실행해 주세요.')
        changes['auto_publish'] = changes.get('delivery',job['delivery']) == 'auto'
        return store.update('jobs',job_id,changes)


def submit(job_id, action):
    with ACTIVE_LOCK:
        job = store.get('jobs', job_id)
        if job_id in ACTIVE:
            raise ValueError('이미 실행 중인 작업입니다.')
        if job['status'] == 'published':
            raise ValueError('이미 게시된 콘텐츠입니다.')
        if action in ('approve','publish') and not job.get('artifact_paths',{}).get('video'):
            raise ValueError('먼저 완성 영상을 만들어 주세요.')
        if action == 'approve' and job['delivery'] != 'approval':
            raise ValueError('승인 후 게시 모드에서 사용할 수 있습니다.')
        if action in ('approve','publish'):
            config = store.settings()
            if not config.get('instagram_token') or not config.get('instagram_user_id'):
                raise ValueError('연결 설정에 Instagram 액세스 토큰과 사용자 ID를 입력해 주세요.')
        if action in ('generate','render','run') and job.get('publish_state'):
            raise ValueError('업로드가 시작된 콘텐츠는 다시 만들 수 없습니다. 재시도로 게시 상태를 확인해 주세요.')
        ACTIVE.add(job_id)
        result = store.event(job_id,'작업을 시작합니다.',status='queued',error=None)
        EXECUTOR.submit(execute,job_id,action)
        return result


def deliver(job_id, force=False, approved=False):
    from .instagram import publish_reel
    job = store.get('jobs',job_id)
    if not force:
        if job['delivery'] == 'export':
            return store.event(job_id,'파일 생성 완료. 영상과 게시 문구를 다운로드할 수 있습니다.',status='ready',progress=100)
        if job['delivery'] == 'approval' and not (approved or job.get('approved_at')):
            return store.event(job_id,'영상 제작 완료. 확인 후 승인하면 게시합니다.',status='ready',progress=100)
        due = parse_time(job.get('scheduled_at'))
        if due and due > datetime.now(timezone.utc):
            return store.event(job_id,'예약됨 · 앱이 실행 중이면 지정 시각에 게시합니다.',status='scheduled',progress=100)
    config = store.settings()
    if not config.get('instagram_token') or not config.get('instagram_user_id'):
        raise ValueError('영상 제작은 완료되었습니다. Instagram 토큰과 사용자 ID를 연결한 뒤 재시도해 주세요.')
    store.event(job_id,'Instagram으로 영상을 업로드하고 있습니다.',status='publishing',progress=92)
    def report(percent,message):
        store.event(job_id,message,progress=min(99,92+int(percent*.07)))
    def persist(state):
        with store.LOCK:
            old = store.get('jobs',job_id).get('publish_state',{})
            store.update('jobs',job_id,{'publish_state':dict(old,**state)})
    result = publish_reel(job,config,Path(job['artifact_paths']['video']),report,persist)
    return store.event(job_id,'Instagram 게시 완료',status='published',progress=100,
                       published_at=store.now(),publication=result,permalink=result.get('permalink'),error=None)


def execute(job_id, action):
    try:
        job = store.get('jobs',job_id)
        if action == 'approve':
            store.update('jobs',job_id,{'approved_at':store.now()})
            deliver(job_id,approved=True)
            return
        if action == 'publish':
            deliver(job_id,force=True)
            return
        if action == 'retry' and job.get('artifact_paths',{}).get('video'):
            deliver(job_id,force=bool(job.get('publish_state')) or job.get('failed_action') == 'publish',
                    approved=job.get('failed_action') == 'approve')
            return
        config = store.settings()
        folder = store.EXPORTS / job_id
        folder.mkdir(parents=True,exist_ok=True)
        def report(percent,message):
            store.event(job_id,message,progress=percent)
        if job['mode'] == 'highlights' and not job.get('transcript_segments'):
            from .highlights import prepare_highlights
            store.event(job_id,'원본 영상과 추출 구간을 준비합니다.',status='generating',progress=3)
            updates = prepare_highlights(job,config,folder,report)
            if updates:
                job = store.update('jobs',job_id,updates)
        if action == 'generate' or not job.get('script'):
            store.event(job_id,'대본을 구성하고 있습니다.',status='generating',progress=8)
            script = generate_script(job,config,report)
            job = store.update('jobs',job_id,{'script':script,'title':script['title'],'artifacts':{},'artifact_paths':{}})
            write_script_bundle(script,folder)
        if action == 'generate':
            store.event(job_id,'대본 작성 완료. 장면을 수정하거나 영상 제작을 시작하세요.',status='draft',progress=25)
            return
        from .media import render_job
        store.event(job_id,'영상·음성·자막을 만들고 있습니다.',status='rendering',progress=25)
        artifacts = render_job(job,config,folder,lambda p,m:report(25+int(p*.65),m))
        paths, public = {}, {}
        for key,value in artifacts.items():
            if isinstance(value,(str,Path)) and Path(str(value)).is_absolute() and Path(str(value)).is_file():
                path = Path(value).resolve()
                paths[key] = str(path)
                public[key] = '/exports/'+path.relative_to(store.EXPORTS).as_posix()
            else:
                public[key] = value
        store.update('jobs',job_id,{'artifact_paths':paths,'artifacts':public})
        if action == 'render':
            store.event(job_id,'영상 제작 완료. 미리보기와 파일을 확인하세요.',status='ready',progress=100)
        else:
            deliver(job_id)
    except Exception as exc:
        store.event(job_id,str(exc),status='failed',error=str(exc),failed_action=action)
    finally:
        with ACTIVE_LOCK:
            ACTIVE.discard(job_id)


def zone(name):
    if name == 'Asia/Seoul':
        return timezone(timedelta(hours=9))
    return ZoneInfo(name)


def save_automation(values, record_id=None):
    old = store.get('automations',record_id) if record_id else {}
    item = dict(old,**values)
    topics = item.get('topics') or []
    if isinstance(topics,str):
        topics = topics.splitlines()
    item['topics'] = [str(t).strip() for t in topics if str(t).strip()]
    if not item['topics']:
        raise ValueError('자동 제작할 주제를 한 줄에 하나씩 입력해 주세요.')
    datetime.strptime(item.get('time','09:00'),'%H:%M')
    zone(item.get('timezone','Asia/Seoul'))
    if item.get('mode','knowledge') not in ('knowledge','product','highlights') or item.get('delivery','export') not in ('export','approval','auto'):
        raise ValueError('자동화 모드 설정을 확인해 주세요.')
    item.update(id=record_id or uuid.uuid4().hex[:12],name=item.get('name') or '매일 릴스 제작',
                created_at=old.get('created_at') or store.now(),updated_at=store.now(),
                enabled=bool(item.get('enabled',False)),time=item.get('time','09:00'),
                timezone=item.get('timezone','Asia/Seoul'),index=int(old.get('index',0)))
    template = item.get('template') or {}
    if template.get('assets'):
        template['assets'] = resolve_assets(template['assets'])
    item['template'] = template
    # A newly enabled rule starts at the next occurrence, never retroactively.
    if item['enabled'] and (not old.get('enabled') or item.get('time') != old.get('time')):
        local = datetime.now(zone(item['timezone']))
        if local.strftime('%H:%M') >= item['time']:
            item['last_run_date'] = local.date().isoformat()
    return store.save('automations',item)


def scheduler_tick():
    for job in store.all_records('jobs'):
        if job['status'] == 'scheduled':
            due = parse_time(job.get('scheduled_at'))
            if due and due <= datetime.now(timezone.utc):
                try:
                    submit(job['id'],'retry')
                except ValueError:
                    pass
    for rule in store.all_records('automations'):
        if not rule.get('enabled'):
            continue
        local = datetime.now(zone(rule.get('timezone','Asia/Seoul')))
        date = local.date().isoformat()
        if rule.get('last_run_date') == date or local.strftime('%H:%M') < rule['time']:
            continue
        with store.LOCK:
            fresh = store.get('automations',rule['id'])
            if fresh.get('last_run_date') == date:
                continue
            index = int(fresh.get('index',0))
            payload = dict(fresh.get('template') or {},topic=fresh['topics'][index % len(fresh['topics'])],
                           mode=fresh.get('mode','knowledge'),delivery=fresh.get('delivery','export'),
                           scheduled_at=None,script=None,automation_id=fresh['id'])
            payload.pop('title',None)
            job = store.new_job(payload)
            store.update('automations',fresh['id'],{'last_run_date':date,'index':index+1,'last_job_id':job['id']})
        submit(job['id'],'run')


def start_scheduler():
    for job in store.all_records('jobs'):
        if job['status'] in BUSY:
            store.event(job['id'],'앱이 종료되어 작업이 중단되었습니다. 재시도하면 이어서 진행합니다.',
                        status='failed',error='이전 실행이 중단되었습니다.')
    def loop():
        while True:
            try:
                scheduler_tick()
            except Exception as exc:
                print('Scheduler:',str(exc),flush=True)
            threading.Event().wait(10)
    threading.Thread(target=loop,daemon=True,name='reel-scheduler').start()
