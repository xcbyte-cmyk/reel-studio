from __future__ import annotations

import argparse
import re
import webbrowser
from functools import lru_cache
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from studio import store, workflow
from studio.assets import receive_upload
from studio.http import HTTPHandler


@lru_cache(maxsize=1)
def capabilities():
    from studio.media import capabilities as get_capabilities
    return get_capabilities()


class Handler(HTTPHandler):
    server_version = 'ReelStudio/1.0'

    def log_message(self, fmt, *args):
        if args and '/api/state' not in str(args[0]) and '/api/jobs/' not in str(args[0]):
            print('%s %s' % (self.log_date_time_string(), fmt % args),flush=True)

    def do_GET(self):
        self.handle_request('GET')

    def do_HEAD(self):
        self.handle_request('HEAD')

    def do_POST(self):
        self.handle_request('POST')

    def do_PATCH(self):
        self.handle_request('PATCH')

    def handle_request(self, method):
        try:
            self.dispatch(method)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            pass
        except (ValueError,KeyError) as exc:
            self.json_response({'error':str(exc)},400)
        except Exception as exc:
            print(type(exc).__name__+': '+str(exc),flush=True)
            self.json_response({'error':str(exc)},500)

    def dispatch(self, method):
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if method in ('GET','HEAD'):
            if path == '/api/health':
                return self.json_response({'ok':True,'name':'Reel Studio'})
            if path == '/api/state':
                return self.json_response({'jobs':[store.public_job(j) for j in store.all_records('jobs')],
                    'settings':store.settings(public=True),'capabilities':capabilities(),
                    'automations':store.all_records('automations')})
            if path == '/api/settings':
                return self.json_response(store.settings(public=True))
            if path == '/api/automations':
                return self.json_response(store.all_records('automations'))
            if re.fullmatch(r'/api/jobs/[a-f0-9]+',path):
                return self.json_response(store.public_job(store.get('jobs',path.split('/')[-1])))
            if path.startswith('/assets/'):
                record = store.get('assets',path.split('/')[2])
                return self.file_response(Path(record['path']),method=='HEAD')
            if path.startswith('/exports/'):
                file = (store.EXPORTS/path[len('/exports/'):]).resolve()
                if not file.is_relative_to(store.EXPORTS.resolve()):
                    raise ValueError('파일 경로를 확인해 주세요.')
                return self.file_response(file,method=='HEAD')
            static = store.ROOT/'static'
            relative = 'index.html' if path == '/' else path.removeprefix('/static/').lstrip('/')
            file = (static/relative).resolve()
            if file.is_relative_to(static.resolve()):
                return self.file_response(file,method=='HEAD')
        if method == 'POST' and path == '/api/assets':
            name = parse_qs(parsed.query).get('name', ['upload'])[0]
            size = int(self.headers.get('Content-Length', 0))
            return self.json_response(receive_upload(self.rfile, name, size), 201)
        if method == 'POST' and path == '/api/settings':
            return self.json_response(store.save_settings(self.body()))
        if method == 'POST' and path == '/api/jobs':
            values = self.body()
            values['assets'] = workflow.resolve_assets(values.get('assets',[]))
            parsed_time = workflow.parse_time(values.get('scheduled_at'))
            values['scheduled_at'] = parsed_time.isoformat() if parsed_time else None
            return self.json_response(store.public_job(store.new_job(values)),201)
        if method == 'POST' and path == '/api/automations':
            return self.json_response(workflow.save_automation(self.body()),201)
        if method == 'PATCH' and re.fullmatch(r'/api/automations/[a-f0-9]+',path):
            return self.json_response(workflow.save_automation(self.body(),path.split('/')[-1]))
        match = re.fullmatch(r'/api/jobs/([a-f0-9]+)(?:/(generate|render|run|approve|publish|retry))?',path)
        if match:
            job_id, action = match.groups()
            if method == 'PATCH' and not action:
                return self.json_response(store.public_job(workflow.edit_job(job_id,self.body())))
            if method == 'POST' and action:
                return self.json_response(store.public_job(workflow.submit(job_id,action)),202)
        return self.json_response({'error':'지원하지 않는 경로입니다.'},404)


def main():
    parser = argparse.ArgumentParser(description='Local Instagram content production studio')
    parser.add_argument('--port',type=int,default=18765)
    parser.add_argument('--open',action='store_true')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    scheduler = workflow.start_scheduler()
    print(f'Reel Studio: http://127.0.0.1:{args.port}',flush=True)
    print('Local daily schedules run while this process is running.',flush=True)
    if args.open:
        webbrowser.open(f'http://127.0.0.1:{args.port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.stop()
        server.server_close()
        workflow.shutdown()


if __name__ == '__main__':
    main()
