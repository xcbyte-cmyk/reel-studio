from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import store
from .assets import resolve_assets


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
    item['time'] = datetime.strptime(item.get('time', '09:00'), '%H:%M').strftime('%H:%M')
    zone(item.get('timezone','Asia/Seoul'))
    if item.get('mode','knowledge') not in ('knowledge','product','highlights') or item.get('delivery','export') not in ('export','approval','auto'):
        raise ValueError('자동화 모드 설정을 확인해 주세요.')
    item.update(id=record_id or uuid.uuid4().hex[:12],name=item.get('name') or '매일 릴스 제작',
                created_at=old.get('created_at') or store.now(),updated_at=store.now(),
                enabled=bool(item.get('enabled',False)),time=item.get('time','09:00'),
                timezone=item.get('timezone','Asia/Seoul'),index=int(old.get('index',0)))
    template = dict(item.get('template') or {})
    if template.get('assets'):
        template['assets'] = resolve_assets(template['assets'])
    item['template'] = template
    # A newly enabled rule starts at the next occurrence, never retroactively.
    if item['enabled'] and (not old.get('enabled') or item['time'] != old.get('time')
                            or item['timezone'] != old.get('timezone')):
        local = datetime.now(zone(item['timezone']))
        if local.strftime('%H:%M') >= item['time']:
            item['last_run_date'] = local.date().isoformat()
    return store.save('automations',item)


def scheduler_tick(submit):
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


class Scheduler:
    """Run daily rules using an injected job submission function."""

    def __init__(self, submit, interval=10):
        self.submit = submit
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name='reel-scheduler')

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join()

    def _run(self):
        while not self._stop.is_set():
            try:
                scheduler_tick(self.submit)
            except Exception as exc:
                print('Scheduler:', str(exc), flush=True)
            self._stop.wait(self.interval)


def start_scheduler(submit):
    return Scheduler(submit).start()
