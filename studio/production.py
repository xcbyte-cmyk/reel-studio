from __future__ import annotations

from pathlib import Path

from . import store
from .content import generate_script, write_script_bundle


def produce(job_id, action):
    """Prepare the script and export media without performing publication."""
    job = store.get('jobs', job_id)
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
