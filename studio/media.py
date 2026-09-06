"""Render complete local reels, measured narration, timed captions and export files."""
from __future__ import annotations

import functools
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import wave
from typing import Callable

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    Image = ImageDraw = ImageFont = ImageOps = None

WIDTH, HEIGHT, FPS = 1080, 1920, 30
INK = (24, 26, 26)
PAPER = (247, 243, 232)
ORANGE = (248, 94, 44)
MUTED = (148, 150, 141)
FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
Progress = Callable[[int, str], None]


def _binary(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if os.name == "nt":
        packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages"
        for candidate in packages.glob(f"*FFmpeg*/**/bin/{name}.exe"):
            return str(candidate)
    return None


@functools.lru_cache(maxsize=1)
def capabilities() -> dict:
    korean_tts = False
    if os.name == "nt" and shutil.which("powershell"):
        try:
            command = "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; @($s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'ko-KR' }).Count; $s.Dispose()"
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, timeout=20, **_process_options(),
            )
            korean_tts = result.returncode == 0 and result.stdout.strip().endswith(tuple("123456789"))
        except (OSError, subprocess.SubprocessError):
            pass
    return {"ffmpeg": bool(_binary("ffmpeg")), "ffprobe": bool(_binary("ffprobe")),
            "pillow": Image is not None, "windows_tts": korean_tts}


def _process_options() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def _report(progress: Progress | None, percent: float, message: str) -> None:
    if progress:
        progress(max(0, min(100, int(percent))), message)


def _probe(path: Path) -> dict:
    command = [_binary("ffprobe") or "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", **_process_options())
    if result.returncode:
        raise RuntimeError(f"미디어 정보를 읽지 못했습니다: {path.name}\n{result.stderr[-1200:]}")
    return json.loads(result.stdout)


def _duration(path: Path) -> float:
    info = _probe(path)
    values = [info.get("format", {}).get("duration")]
    values.extend(stream.get("duration") for stream in info.get("streams", []))
    for value in values:
        try:
            duration = float(value)
            if duration > 0 and math.isfinite(duration):
                return duration
        except (ValueError, TypeError):
            continue
    raise RuntimeError(f"미디어 길이를 확인할 수 없습니다: {path.name}")


def _ffmpeg(args: list[str], progress: Progress | None = None, start: float = 0,
            span: float = 0, duration: float = 0, message: str = "영상 렌더링 중") -> None:
    command = [_binary("ffmpeg") or "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1", *args]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", **_process_options())
    lines: list[str] = []
    try:
        for line in process.stdout:
            line = line.strip()
            if line.startswith("out_time_us=") and duration:
                try:
                    position = float(line.split("=", 1)[1]) / 1_000_000
                    _report(progress, start + span * min(1, position / duration), message)
                except ValueError:
                    pass
            elif line and not re.match(r"^(frame|fps|stream_\d+_\d+_q|bitrate|total_size|out_time|dup_frames|drop_frames|speed|progress)=", line):
                lines.append(line)
                lines = lines[-30:]
        code = process.wait()
    finally:
        if process.stdout:
            process.stdout.close()
    if code:
        raise RuntimeError("FFmpeg 렌더링 실패: " + "\n".join(lines)[-3000:])


@functools.lru_cache(maxsize=64)
def _font(size: int, bold: bool = False):
    paths = [FONT_DIR / ("malgunbd.ttf" if bold else "malgun.ttf"),
             Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf" if bold else "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
             Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")]
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError("한국어 글꼴을 찾을 수 없습니다. 맑은 고딕 또는 Noto Sans CJK 글꼴을 설치하세요.")


def _wrap(text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and font.getlength(candidate) > width:
                if " " in current and not re.search(r"[가-힣]", current):
                    head, tail = current.rsplit(" ", 1)
                    if head:
                        lines.append(head)
                        current = tail + char
                        continue
                lines.append(current.rstrip())
                current = char.lstrip()
            else:
                current = candidate
        lines.append(current.rstrip())
    return lines


def _text_box(draw, text: str, box: tuple[int, int, int, int], size: int,
              fill=PAPER, bold: bool = True, align: str = "left", spacing: float = 1.30):
    x, y, width, height = box
    chosen = max(12, int(size))
    while True:
        font = _font(chosen, bold)
        lines = _wrap(text, font, width)
        line_height = int(chosen * spacing)
        if len(lines) * line_height <= height or chosen <= 12:
            break
        chosen -= 2
    for index, line in enumerate(lines):
        px = x + (width - font.getlength(line)) / 2 if align == "center" else x
        draw.text((px, y + index * line_height), line, font=font, fill=fill, anchor="lt")
    return len(lines) * line_height


def _label(draw, text: str, xy: tuple[int, int], fill=ORANGE, size=26):
    draw.text(xy, str(text), font=_font(size, True), fill=fill, anchor="lt")


def _chunk_text(text: str, limit: int = 54) -> list[str]:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?。！？])\s+|(?<=[。！？])", text)
    chunks: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip()
        while len(sentence) > limit:
            choices = [sentence.rfind(mark, limit // 2, limit + 1) for mark in (" ", ",", "，", ";")]
            split_at = max(choices)
            split_at = split_at + 1 if split_at >= limit // 2 else limit
            chunks.append(sentence[:split_at].strip())
            sentence = sentence[split_at:].strip()
        if sentence:
            if chunks and len(chunks[-1]) + len(sentence) < 34:
                chunks[-1] += " " + sentence
            else:
                chunks.append(sentence)
    return chunks


def _caption(draw, text: str, dark: bool = True) -> None:
    if not text:
        return
    color = (17, 19, 19, 224) if dark else (255, 255, 255, 235)
    draw.rounded_rectangle((74, 1470, 1006, 1694), radius=24, fill=color)
    _text_box(draw, text, (109, 1502, 862, 162), 42,
              fill=PAPER if dark else INK, bold=True, align="center", spacing=1.28)


def _knowledge_frame(job: dict, scene: dict, index: int, total: int, caption: str = ""):
    canvas = Image.new("RGB", (WIDTH, HEIGHT), INK)
    draw = ImageDraw.Draw(canvas)
    brand = str(job.get("brand") or "REEL STUDIO")
    _text_box(draw, brand, (84, 126, 735, 65), 30, fill=PAPER)
    draw.ellipse((938, 126, 962, 150), fill=ORANGE)
    draw.line((84, 232, 996, 232), fill=(77, 79, 75), width=2)
    _label(draw, f"{index + 1:02d} / {total:02d}", (84, 288), size=27)
    _label(draw, "INSIGHT" if index == 0 else "TAKE NOTE", (762, 288), fill=MUTED, size=24)
    draw.rounded_rectangle((84, 408, 100, 516), radius=8, fill=ORANGE)
    text = str(scene.get("text") or scene.get("narration") or job.get("title") or "새로운 이야기")
    _text_box(draw, text, (136, 408, 855, 775), 104 if index == 0 else 87, fill=PAPER)
    draw.line((84, 1270, 996, 1270), fill=(77, 79, 75), width=2)
    footer = str(job.get("cta") or "저장하고 다음 이야기에서 만나요") if index == total - 1 else str(job.get("topic") or job.get("title") or "")
    _text_box(draw, footer, (84, 1310, 910, 100), 30, fill=MUTED, bold=False)
    _caption(draw, caption)
    _label(draw, "REEL / KNOWLEDGE", (84, 1778), fill=MUTED, size=24)
    draw.rounded_rectangle((84, 1848, 996, 1854), radius=3, fill=(72, 75, 70))
    draw.rounded_rectangle((84, 1848, 84 + int(912 * (index + 1) / total), 1854), radius=3, fill=ORANGE)
    return canvas


def _product_overlay(job: dict, scene: dict, index: int, total: int, caption: str = ""):
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for y in range(380):
        draw.line((0, y, WIDTH, y), fill=(15, 18, 18, max(0, int(190 * (1 - y / 380)))))
    draw.rectangle((0, 1050, WIDTH, HEIGHT), fill=INK + (255,))
    for y in range(180):
        draw.line((0, 870 + y, WIDTH, 870 + y), fill=INK + (int(255 * y / 180),))
    _text_box(draw, str(job.get("brand") or "REEL STUDIO"), (74, 116, 790, 55), 29, fill=PAPER)
    draw.rounded_rectangle((900, 106, 1004, 172), radius=30, fill=ORANGE)
    _label(draw, f"{index + 1:02d}", (930, 122), fill=INK, size=27)
    _label(draw, "IN FOCUS", (74, 990), size=27)
    draw.rounded_rectangle((58, 1084, 1022, 1424), radius=30, fill=PAPER)
    _text_box(draw, str(scene.get("text") or job.get("title") or "상품의 디테일"),
              (96, 1123, 888, 264), 68, fill=INK)
    _caption(draw, caption)
    footer = str(job.get("cta") or "자세한 내용은 프로필에서") if index == total - 1 else str(job.get("title") or "")
    _text_box(draw, footer, (74, 1760, 930, 77), 29, fill=PAPER, bold=False)
    draw.rectangle((74, 1847, 1006, 1853), fill=(76, 79, 74))
    draw.rectangle((74, 1847, 74 + int(932 * (index + 1) / total), 1853), fill=ORANGE)
    return canvas


def _highlight_overlay(job: dict, caption: str = ""):
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for y in range(410):
        draw.line((0, y, WIDTH, y), fill=(12, 15, 15, max(0, int(208 * (1 - y / 410)))))
    _text_box(draw, str(job.get("brand") or "REEL STUDIO"), (76, 113, 780, 50), 28, fill=PAPER)
    draw.rounded_rectangle((76, 202, 1004, 403), radius=22, fill=(20, 23, 23, 174))
    draw.rounded_rectangle((76, 202, 86, 403), radius=5, fill=ORANGE)
    _text_box(draw, str(job.get("title") or job.get("topic") or "HIGHLIGHT"), (114, 232, 850, 149), 58, fill=PAPER)
    _caption(draw, caption)
    return canvas


def _image_background(path: Path):
    with Image.open(path) as source:
        source = ImageOps.exif_transpose(source).convert("RGB")
        return ImageOps.fit(source, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)


def _asset_is_video(asset: dict) -> bool:
    kind = str(asset.get("kind") or "").lower()
    return kind.startswith("video") or Path(str(asset.get("path", ""))).suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def _asset_is_image(asset: dict) -> bool:
    kind = str(asset.get("kind") or "").lower()
    return kind.startswith("image") or Path(str(asset.get("path", ""))).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}


def _concat_quote(path: Path) -> str:
    return "'" + path.resolve().as_posix().replace("'", "'\\''") + "'"


def _playlist(work_dir: Path, prefix: str, duration: float, subtitles: list[dict], factory) -> Path:
    boundaries = sorted({0.0, duration, *[max(0, min(duration, float(s[key]))) for s in subtitles for key in ("start", "end")]})
    files: dict[str, Path] = {}
    entries: list[str] = ["ffconcat version 1.0"]
    last = None
    for start, end in zip(boundaries, boundaries[1:]):
        if end - start < .001:
            continue
        middle = (start + end) / 2
        text = " ".join(s["text"] for s in subtitles if s["start"] <= middle < s["end"])
        if text not in files:
            frame_path = work_dir / f"{prefix}-{len(files):03d}.png"
            factory(text).save(frame_path)
            files[text] = frame_path
        last = files[text]
        entries.extend([f"file {_concat_quote(last)}", f"duration {end - start:.6f}"])
    if last:
        entries.append(f"file {_concat_quote(last)}")
    path = work_dir / f"{prefix}.ffconcat"
    path.write_text("\n".join(entries) + "\n", encoding="utf-8")
    return path


def _windows_speech(items: list[dict], work_dir: Path) -> None:
    helper = Path(__file__).with_name("windows_tts.ps1")
    input_path = work_dir / "speech-request.json"
    input_path.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8-sig")
    if not shutil.which("powershell"):
        raise RuntimeError("Windows 음성 합성을 사용할 수 없습니다. 설정에서 OpenAI 또는 음성 없음을 선택하세요.")
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(helper), "-InputJson", str(input_path)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=max(120, len(items) * 25), **_process_options())
    if result.returncode:
        raise RuntimeError("Windows 음성 생성에 실패했습니다: " + result.stderr[-1600:])


def _openai_speech(items: list[dict], settings: dict, progress: Progress | None):
    import requests
    key = str(settings.get("openai_api_key") or "").strip()
    if not key:
        raise RuntimeError("OpenAI 음성을 사용하려면 설정에 OpenAI API 키를 입력하세요.")
    with requests.Session() as session:
        for index, item in enumerate(items):
            response = session.post("https://api.openai.com/v1/audio/speech", headers={"Authorization": f"Bearer {key}"},
                                    json={"model": settings.get("openai_tts_model") or "gpt-4o-mini-tts",
                                          "voice": settings.get("openai_voice") or "coral", "input": item["text"], "response_format": "wav"}, timeout=180)
            if not response.ok:
                try:
                    reason = response.json().get("error", {}).get("message", response.text[:800])
                except ValueError:
                    reason = response.text[:800]
                raise RuntimeError(f"OpenAI 음성 생성 실패 ({response.status_code}): {reason}")
            Path(item["path"]).write_bytes(response.content)
            _report(progress, 8 + 18 * (index + 1) / max(1, len(items)), f"내레이션 생성 {index + 1}/{len(items)}")


def _silent_wav(path: Path, duration: float, rate: int = 24000):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        remaining = int(math.ceil(duration * rate))
        block = b"\0" * (rate * 2)
        while remaining:
            frames = min(remaining, rate)
            output.writeframesraw(block[:frames * 2])
            remaining -= frames


def _assemble_audio(items: list[dict], path: Path, desired_duration: float) -> tuple[float, list[dict]]:
    chunks: list[tuple[dict, bytes, tuple]] = []
    for item in items:
        with wave.open(item["path"], "rb") as audio:
            chunks.append((item, audio.readframes(audio.getnframes()), (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())))
    channels, sample_width, rate = chunks[0][2]
    frame_size = channels * sample_width
    cursor = int(rate * .10)
    subtitles = []
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.setframerate(rate)
        output.writeframesraw(b"\0" * (cursor * frame_size))
        for item, frames, params in chunks:
            if params != (channels, sample_width, rate):
                raise RuntimeError("음성 파일 형식이 일치하지 않습니다. 같은 음성 설정으로 다시 생성하세요.")
            start = cursor / rate
            output.writeframesraw(frames)
            cursor += len(frames) // frame_size
            pause = int(rate * .16)
            output.writeframesraw(b"\0" * (pause * frame_size))
            cursor += pause
            subtitles.append({"start": start, "end": cursor / rate, "text": item["text"]})
        total = max(desired_duration, cursor / rate + .12)
        total = math.ceil(total * FPS) / FPS
        extra = max(0, int(total * rate) - cursor)
        while extra:
            count = min(extra, rate)
            output.writeframesraw(b"\0" * (count * frame_size))
            extra -= count
    return total, subtitles


def _srt_timestamp(seconds: float) -> str:
    value = max(0, round(seconds * 1000))
    hours, value = divmod(value, 3_600_000)
    minutes, value = divmod(value, 60_000)
    seconds, milliseconds = divmod(value, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _export_artifacts(job: dict, output_dir: Path, duration: float, subtitles: list[dict], warnings: list[str], extra: dict | None = None) -> dict:
    script = dict(job.get("script") or {})
    script.update({"rendered_duration": round(duration, 3), "mode": job.get("mode", "knowledge")})
    if extra:
        script.update(extra)
    (output_dir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    caption = str(script.get("caption") or "").strip()
    tags = " ".join("#" + str(tag).strip().lstrip("#").replace(" ", "") for tag in script.get("hashtags", []) if str(tag).strip())
    if tags:
        caption = caption + "\n\n" + tags if caption else tags
    (output_dir / "caption.txt").write_text(caption + "\n", encoding="utf-8")
    entries = [f"{index}\n{_srt_timestamp(item['start'])} --> {_srt_timestamp(item['end'])}\n{item['text']}\n" for index, item in enumerate(subtitles, 1)]
    (output_dir / "subtitles.srt").write_text("\n".join(entries), encoding="utf-8-sig")
    return {"video": str((output_dir / "reel.mp4").resolve()), "cover": str((output_dir / "cover.png").resolve()),
            "subtitles": str((output_dir / "subtitles.srt").resolve()), "script": str((output_dir / "script.json").resolve()),
            "caption": str((output_dir / "caption.txt").resolve()), "duration": round(duration, 3),
            "warnings": warnings, "width": WIDTH, "height": HEIGHT, "fps": FPS, "subtitle_count": len(subtitles)}


def _encoder_args() -> list[str]:
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-threads", "4", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart"]


def _video_cover(source: Path, at: float, destination: Path) -> None:
    _ffmpeg(["-ss", f"{at:.4f}", "-i", str(source), "-frames:v", "1", "-vf",
             f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1", str(destination)])


def _render_highlights(job: dict, settings: dict, output_dir: Path, work_dir: Path, progress: Progress | None) -> dict:
    videos = [asset for asset in job.get("assets", []) if _asset_is_video(asset) and Path(str(asset.get("path", ""))).is_file()]
    if not videos:
        raise ValueError("하이라이트 모드에는 원본 동영상 파일을 업로드하세요.")
    source = Path(videos[0]["path"])
    info = _probe(source)
    source_duration = _duration(source)
    wanted = max(1.0, float(job.get("duration") or 30))
    explicit = job.get("clip_start") is not None or job.get("clip_end") is not None
    start = max(0.0, float(job.get("clip_start") or 0)) if explicit else max(0, (source_duration - wanted) / 2)
    end = float(job.get("clip_end")) if job.get("clip_end") not in (None, "") else start + wanted
    end = min(source_duration, end)
    if start >= source_duration or end <= start:
        raise ValueError(f"하이라이트 구간이 올바르지 않습니다. 원본 길이: {source_duration:.2f}초")
    duration = end - start
    subtitles = []
    for segment in job.get("transcript_segments") or []:
        seg_start, seg_end = float(segment.get("start", 0)), float(segment.get("end", 0))
        if seg_end <= start or seg_start >= end or seg_end <= seg_start:
            continue
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        pieces = _chunk_text(text)
        weight = sum(len(piece) for piece in pieces) or 1
        cursor = seg_start
        for piece in pieces:
            piece_end = cursor + (seg_end - seg_start) * len(piece) / weight
            low, high = max(0, cursor - start), min(duration, piece_end - start)
            if high > low:
                subtitles.append({"start": low, "end": high, "text": piece})
            cursor = piece_end
    subtitles.sort(key=lambda entry: entry["start"])
    warnings = []
    if not explicit:
        warnings.append("원본의 가운데 구간을 추출했습니다. 의미를 분석해 선택한 장면이 아닙니다.")
    if not subtitles:
        warnings.append("원본 음성을 보존했습니다. 실제 전사 데이터가 없어 대사 자막과 SRT 내용은 생성하지 않았습니다.")
    playlist = _playlist(work_dir, "highlight", duration, subtitles, lambda text: _highlight_overlay(job, text))
    _report(progress, 14, f"원본 {start:.1f}–{end:.1f}초 구간 편집 중")
    has_audio = any(stream.get("codec_type") == "audio" for stream in info.get("streams", []))
    args = ["-ss", f"{start:.6f}", "-i", str(source), "-f", "concat", "-safe", "0", "-i", str(playlist)]
    if not has_audio:
        args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        warnings.append("원본에 오디오 트랙이 없어 무음 AAC 트랙으로 내보냈습니다.")
    args += ["-filter_complex", f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS},setpts=PTS-STARTPTS[bg];[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
             "-map", "[v]", "-map", "0:a:0" if has_audio else "2:a:0", "-af", "asetpts=PTS-STARTPTS,apad", "-t", f"{duration:.6f}", *_encoder_args(), str(output_dir / "reel.mp4")]
    _ffmpeg(args, progress, 15, 80, duration, "하이라이트 영상과 원본 음성 내보내는 중")
    _video_cover(source, start + min(1.0, duration / 2), work_dir / "source-cover.png")
    cover = Image.open(work_dir / "source-cover.png").convert("RGBA")
    cover = Image.alpha_composite(cover, _highlight_overlay(job, ""))
    cover.convert("RGB").save(output_dir / "cover.png")
    result = _export_artifacts(job, output_dir, _duration(output_dir / "reel.mp4"), subtitles, warnings,
                               {"clip_start": start, "clip_end": end, "original_audio_preserved": has_audio})
    _report(progress, 100, "하이라이트 영상·커버·자막 내보내기 완료")
    return result


def render_job(job: dict, settings: dict, output_dir: Path, progress: Progress | None = None) -> dict:
    """Build reel.mp4 and companion files; return absolute artifact paths."""
    if Image is None:
        raise RuntimeError("Pillow가 설치되어 있지 않습니다. requirements.txt의 패키지를 설치하세요.")
    if not _binary("ffmpeg") or not _binary("ffprobe"):
        raise RuntimeError("FFmpeg와 FFprobe가 필요합니다. 설치 후 앱을 다시 실행하세요.")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = output_dir.parent.parent / "work" / f"render-{output_dir.name}"
    work_dir.mkdir(parents=True, exist_ok=True)
    mode = str(job.get("mode") or "knowledge")
    if mode == "highlights":
        return _render_highlights(job, settings, output_dir, work_dir, progress)
    if mode not in {"knowledge", "product"}:
        raise ValueError(f"지원하지 않는 콘텐츠 모드: {mode}")
    script = job.get("script") or {}
    scenes = [dict(scene) for scene in script.get("scenes", []) if isinstance(scene, dict)]
    if not scenes:
        raise ValueError("렌더링할 대본 장면이 없습니다. 먼저 대본을 생성하세요.")
    assets = [asset for asset in job.get("assets", []) if (_asset_is_video(asset) or _asset_is_image(asset)) and Path(str(asset.get("path", ""))).is_file()]
    if mode == "product" and not assets:
        raise ValueError("상품 모드에는 상품 사진 또는 동영상 파일을 업로드하세요.")
    provider = str(settings.get("tts_provider") or "windows").lower()
    if provider not in {"windows", "openai", "none"}:
        raise ValueError(f"지원하지 않는 음성 제공자: {provider}")
    desired_total = max(1.0, float(job.get("duration") or 30))
    desired_per_scene = desired_total / len(scenes)
    speech_items = []
    plans = []
    for index, scene in enumerate(scenes):
        narration = str(scene.get("narration") or scene.get("text") or "").strip()
        items = [{"text": text, "path": str(work_dir / f"voice-{index:03d}-{chunk:03d}.wav")} for chunk, text in enumerate(_chunk_text(narration))]
        speech_items.extend(items)
        plans.append({"scene": scene, "items": items, "desired": max(.5, float(scene.get("duration") or desired_per_scene))})
    _report(progress, 5, "장면별 내레이션과 자막 준비 중")
    if speech_items and provider == "windows":
        _report(progress, 8, "Windows 한국어 음성 생성 중")
        _windows_speech(speech_items, work_dir)
    elif speech_items and provider == "openai":
        _openai_speech(speech_items, settings, progress)
    warnings = []
    if provider == "none":
        warnings.append("음성 없음 설정으로 내레이션 없이 렌더링했습니다. 자막은 대본의 표시 시간을 따릅니다.")
    total = 0.0
    for index, plan in enumerate(plans):
        audio_path = work_dir / f"scene-{index:03d}.wav"
        if provider != "none" and plan["items"]:
            duration, subtitles = _assemble_audio(plan["items"], audio_path, plan["desired"])
        else:
            duration = math.ceil(plan["desired"] * FPS) / FPS
            _silent_wav(audio_path, duration)
            weight = sum(len(item["text"]) for item in plan["items"]) or 1
            cursor = 0.0
            subtitles = []
            for item in plan["items"]:
                end = cursor + duration * len(item["text"]) / weight
                subtitles.append({"start": cursor, "end": end, "text": item["text"]})
                cursor = end
        plan.update({"audio": audio_path, "duration": duration, "subtitles": subtitles, "start": total})
        total += duration
    if total > desired_total + 1:
        warnings.append(f"대본 전체를 읽을 수 있도록 요청한 {desired_total:.0f}초에서 {total:.1f}초로 길이를 늘렸습니다.")
    _report(progress, 28, f"{len(plans)}개 장면 · {total:.1f}초 영상 구성 중")
    all_subtitles = []
    scene_files = []
    for index, plan in enumerate(plans):
        scene, duration = plan["scene"], plan["duration"]
        asset = assets[index % len(assets)] if mode == "product" else None
        video_asset = asset is not None and _asset_is_video(asset)
        background = _image_background(Path(asset["path"])) if asset and not video_asset else None
        def factory(text, i=index, scene=scene, bg=background):
            if mode == "knowledge":
                return _knowledge_frame(job, scene, i, len(plans), text)
            overlay = _product_overlay(job, scene, i, len(plans), text)
            return Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB") if bg is not None else overlay
        playlist = _playlist(work_dir, f"scene-{index:03d}", duration, plan["subtitles"], factory)
        if index == 0:
            if video_asset:
                _video_cover(Path(asset["path"]), 0, work_dir / "product-cover.png")
                with Image.open(work_dir / "product-cover.png") as picture:
                    cover = Image.alpha_composite(picture.convert("RGBA"), _product_overlay(job, scene, index, len(plans)))
                    cover.convert("RGB").save(output_dir / "cover.png")
            else:
                factory("").convert("RGB").save(output_dir / "cover.png")
        target = work_dir / f"scene-{index:03d}.mp4"
        if video_asset:
            args = ["-stream_loop", "-1", "-i", str(asset["path"]), "-f", "concat", "-safe", "0", "-i", str(playlist), "-i", str(plan["audio"]),
                    "-filter_complex", f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS},setpts=PTS-STARTPTS[bg];[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]", "-map", "[v]", "-map", "2:a:0"]
        else:
            args = ["-f", "concat", "-safe", "0", "-i", str(playlist), "-i", str(plan["audio"]), "-vf", f"fps={FPS},setsar=1,format=yuv420p", "-map", "0:v:0", "-map", "1:a:0"]
        args += ["-t", f"{duration:.6f}", *_encoder_args(), str(target)]
        _ffmpeg(args, progress, 30 + 60 * plan["start"] / total, 60 * duration / total, duration, f"장면 {index + 1}/{len(plans)} 렌더링 중")
        scene_files.append(target)
        all_subtitles.extend({"start": item["start"] + plan["start"], "end": item["end"] + plan["start"], "text": item["text"]} for item in plan["subtitles"])
    combined = work_dir / "combined.ffconcat"
    combined.write_text("ffconcat version 1.0\n" + "\n".join(f"file {_concat_quote(path)}" for path in scene_files) + "\n", encoding="utf-8")
    _report(progress, 92, "최종 MP4와 내보내기 파일 저장 중")
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(combined), "-c", "copy", "-movflags", "+faststart", str(output_dir / "reel.mp4")], progress, 92, 5, total, "최종 영상 합치는 중")
    actual_duration = _duration(output_dir / "reel.mp4")
    result = _export_artifacts(job, output_dir, actual_duration, all_subtitles, warnings,
                               {"rendered_scenes": [{"start": round(plan["start"], 4), "duration": round(plan["duration"], 4), "text": plan["scene"].get("text", ""), "narration": plan["scene"].get("narration", "")} for plan in plans], "tts_provider": provider})
    _report(progress, 100, "영상·커버·자막·대본 내보내기 완료")
    return result
