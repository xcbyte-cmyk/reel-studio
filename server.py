from __future__ import annotations

import argparse
import json
import mimetypes
import re
import uuid
import webbrowser
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from studio import store, workflow


@lru_cache(maxsize=1)
def capabilities():
    from studio.media import capabilities as get_capabilities
    return get_capabilities()


class Handler(BaseHTTPRequestHandler):
    server_version = 'ReelStudio/1.0'

    def log_message(self, fmt, *args):
        if args and '/api/state' not in str(args[0]) and '/api/jobs/' not in str(args[0]):
            print('%s %s' % (self.log_date_time_string(), fmt % args),flush=True)

    def json_response(self, value, code=200):
        raw = json.dumps(value,ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        length = int(self.headers.get('Content-Length',0))
        if length > 8 * 1024 * 1024:
            raise ValueError('요청 데이터가 너무 큽니다. 파일은 업로드 기능을 사용해 주세요.')
        return json.loads(self.rfile.read(length).decode('utf-8')) if length else {}

    def file_response(self, path, head=False):
        if not path.is_file():
            return self.json_response({'error':'파일을 찾을 수 없습니다.'},404)
        size = path.stat().st_size
        start, end = 0, size-1
        range_header = self.headers.get('Range','')
        match = re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
        if match:
            if match[1]:
                start = int(match[1])
                end = min(int(match[2]),size-1) if match[2] else size-1
            elif match[2]:
                start = max(0,size-int(match[2]))
            if start >= size or end < start:
                self.send_response(416)
                self.send_header('Content-Range',f'bytes */{size}')
                self.end_headers()
                return
        self.send_response(206 if match else 200)
        self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length',str(max(0,end-start+1)))
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Cache-Control','no-cache')
        if match:
            self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        if head:
            return
        with path.open('rb') as source:
            source.seek(start)
            remaining = end-start+1
            while remaining > 0:
                chunk = source.read(min(1024*1024,remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

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
            name = Path(parse_qs(parsed.query).get('name',['upload'])[0]).name
            extension = Path(name).suffix.lower()
            kind = 'image' if extension in ('.jpg','.jpeg','.png','.webp','.bmp') else 'video' if extension in ('.mp4','.mov','.mkv','.webm','.avi','.m4v') else 'audio' if extension in ('.mp3','.wav','.m4a','.aac') else None
            if not kind:
                raise ValueError('지원 형식: JPG, PNG, WEBP, BMP, MP4, MOV, MKV, WEBM, AVI, MP3, WAV, M4A, AAC')
            size = int(self.headers.get('Content-Length',0))
            if not 0 < size <= 2*1024**3:
                raise ValueError('최대 2GB의 파일을 업로드할 수 있습니다.')
            asset_id = uuid.uuid4().hex[:12]
            file = store.DATA/'assets'/(asset_id+extension)
            with file.open('wb') as output:
                remaining = size
                while remaining:
                    chunk = self.rfile.read(min(1024*1024,remaining))
                    if not chunk:
                        raise ValueError('파일 업로드가 중단되었습니다.')
                    output.write(chunk)
                    remaining -= len(chunk)
            record = {'id':asset_id,'name':name,'kind':kind,'size':size,'path':str(file),
                      'url':'/assets/'+asset_id+'/'+name}
            store.save('assets',record)
            return self.json_response({k:v for k,v in record.items() if k!='path'},201)
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
    workflow.start_scheduler()
    print(f'Reel Studio: http://127.0.0.1:{args.port}',flush=True)
    print('Local daily schedules run while this process is running.',flush=True)
    if args.open:
        webbrowser.open(f'http://127.0.0.1:{args.port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == '__main__':
    main()
