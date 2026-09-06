from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler


class HTTPHandler(BaseHTTPRequestHandler):
    """Shared JSON and byte-range responses for the local HTTP API."""

    def json_response(self, value, code=200):
        raw = json.dumps(value,ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def body(self):
        length = int(self.headers.get('Content-Length',0))
        if length > 8 * 1024 * 1024:
            raise ValueError('요청 데이터가 너무 큽니다. 파일은 업로드 기능을 사용해 주세요.')
        value = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
        if not isinstance(value, dict):
            raise ValueError('요청 데이터는 JSON 객체여야 합니다.')
        return value

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
