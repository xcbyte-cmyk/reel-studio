from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO

from . import store


def resolve_assets(assets):
    return [store.get('assets', a['id']) for a in assets]


def receive_upload(source: BinaryIO, name: str, size: int) -> dict:
    """Stream a supported upload to disk and register the completed asset."""
    name = Path(name).name
    extension = Path(name).suffix.lower()
    kind = 'image' if extension in ('.jpg','.jpeg','.png','.webp','.bmp') else 'video' if extension in ('.mp4','.mov','.mkv','.webm','.avi','.m4v') else 'audio' if extension in ('.mp3','.wav','.m4a','.aac') else None
    if not kind:
        raise ValueError('지원 형식: JPG, PNG, WEBP, BMP, MP4, MOV, MKV, WEBM, AVI, MP3, WAV, M4A, AAC')
    if not 0 < size <= 2*1024**3:
        raise ValueError('최대 2GB의 파일을 업로드할 수 있습니다.')
    asset_id = uuid.uuid4().hex[:12]
    file = store.DATA/'assets'/(asset_id+extension)
    try:
        with file.open('wb') as output:
            remaining = size
            while remaining:
                chunk = source.read(min(1024*1024, remaining))
                if not chunk:
                    raise ValueError('파일 업로드가 중단되었습니다.')
                output.write(chunk)
                remaining -= len(chunk)
    except Exception:
        file.unlink(missing_ok=True)
        raise
    record = {'id':asset_id,'name':name,'kind':kind,'size':size,'path':str(file),
              'url':'/assets/'+asset_id+'/'+name}
    store.save('assets',record)
    return {key: value for key, value in record.items() if key != 'path'}
