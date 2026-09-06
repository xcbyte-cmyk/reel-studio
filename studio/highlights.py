"""Transcribe a source recording and select a contiguous, timestamped excerpt."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import requests


CHUNK_SECONDS = 600
PROMPT_CHARACTERS = 26000
API_ROOT = "https://api.openai.com/v1"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}


def _report(progress, percent, message):
    if progress:
        progress(int(percent), message)


def _write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _source(job):
    for asset in job.get("assets", []):
        path = Path(asset.get("path") or "")
        if asset.get("kind") == "video" or path.suffix.lower() in VIDEO_EXTENSIONS:
            if not path.is_file():
                raise ValueError("하이라이트 원본 파일을 찾을 수 없습니다. 동영상을 다시 추가해 주세요.")
            return path.resolve()
    raise ValueError("하이라이트를 추출할 원본 동영상을 추가해 주세요.")


def _run(command, timeout):
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, **options)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("원본 영상의 오디오 처리가 제한 시간을 초과했습니다.") from exc
    if result.returncode:
        raise RuntimeError("원본 영상의 오디오 처리 실패: " + result.stderr.strip()[-1200:])
    return result.stdout


def _probe(source):
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("자동 하이라이트 추출에는 FFmpeg와 ffprobe가 필요합니다.")
    data = json.loads(_run([executable, "-v", "error", "-show_format", "-show_streams",
                            "-of", "json", str(source)], 120))
    values = [data.get("format", {}).get("duration")]
    values.extend(stream.get("duration") for stream in data.get("streams", []))
    durations = []
    for value in values:
        try:
            number = float(value)
            if math.isfinite(number) and number > 0:
                durations.append(number)
        except (TypeError, ValueError):
            continue
    if not durations:
        raise ValueError("원본 동영상의 재생 시간을 확인할 수 없습니다.")
    duration = durations[0]
    audio = any(stream.get("codec_type") == "audio" for stream in data.get("streams", []))
    return duration, audio


def _response_json(response, stage):
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{stage}: OpenAI 응답을 읽을 수 없습니다 (HTTP {response.status_code}).") from exc
    if not response.ok:
        error = data.get("error") or {}
        detail = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        raise RuntimeError(f"{stage}: {detail or 'OpenAI 요청 실패'} (HTTP {response.status_code})")
    return data


def _transcribe(audio_path, key, offset, length):
    with audio_path.open("rb") as audio:
        response = requests.post(
            API_ROOT + "/audio/transcriptions",
            headers={"Authorization": "Bearer " + key},
            files={"file": (audio_path.name, audio, "audio/mpeg")},
            data={"model": "whisper-1", "response_format": "verbose_json",
                  "timestamp_granularities[]": "segment"},
            timeout=(30, 900),
        )
    data = _response_json(response, "원본 음성 전사")
    segments = []
    for item in data.get("segments", []):
        text = str(item.get("text") or "").strip()
        try:
            start, end = float(item["start"]), float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not text or not math.isfinite(start) or not math.isfinite(end):
            continue
        start, end = max(0.0, start), min(length, end)
        if end > start:
            segments.append({"start": round(offset + start, 3),
                             "end": round(offset + end, 3), "text": text})
    if data.get("text", "").strip() and not segments:
        raise RuntimeError("음성 전사에서 구간별 타임스탬프를 받지 못했습니다. 다시 시도해 주세요.")
    return segments


def _transcript(source, duration, settings, output_dir, progress):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("자동 하이라이트 추출에는 FFmpeg가 필요합니다.")
    cache_path = output_dir / "transcript.json"
    stat = source.stat()
    identity = {"path": str(source), "size": stat.st_size, "modified_ns": stat.st_mtime_ns,
                "duration": duration, "chunk_seconds": CHUNK_SECONDS, "model": "whisper-1"}
    cache = {"source": identity, "chunks": {}, "segments": [], "complete": False}
    if cache_path.exists():
        try:
            previous = json.loads(cache_path.read_text(encoding="utf-8"))
            if previous.get("source") == identity:
                cache = previous
        except (OSError, ValueError):
            pass
    chunk_count = math.ceil(duration / CHUNK_SECONDS)
    chunks = cache.setdefault("chunks", {})
    for index in range(chunk_count):
        offset = index * CHUNK_SECONDS
        length = min(CHUNK_SECONDS, duration - offset)
        _report(progress, 5 + 62 * index / chunk_count,
                f"전체 원본 음성 분석 {index + 1}/{chunk_count} · {offset / 60:.1f}분부터")
        if str(index) in chunks:
            continue
        audio_path = output_dir / f"transcription-{index:05d}.mp3"
        _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(offset),
              "-i", str(source), "-t", str(length), "-map", "0:a:0", "-vn",
              "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "32k",
              str(audio_path)], 1200)
        chunks[str(index)] = _transcribe(audio_path, settings["openai_api_key"], offset, length)
        cache["segments"] = [segment for i in range(chunk_count)
                             for segment in chunks.get(str(i), [])]
        cache["complete"] = len(chunks) == chunk_count
        _write_json(cache_path, cache)
        audio_path.unlink(missing_ok=True)
    segments = [segment for index in range(chunk_count) for segment in chunks[str(index)]]
    segments.sort(key=lambda item: (item["start"], item["end"]))
    if not segments:
        raise ValueError("원본에서 인식 가능한 발화를 찾지 못했습니다. 시작·종료 시간을 직접 지정해 주세요.")
    return segments


def _structured(settings, instruction, prompt, name, properties):
    response = requests.post(
        API_ROOT + "/responses",
        headers={"Authorization": "Bearer " + settings["openai_api_key"]},
        json={"model": settings.get("openai_model") or "gpt-4.1-mini", "store": False,
              "instructions": instruction, "input": prompt, "max_output_tokens": 4096,
              "text": {"format": {"type": "json_schema", "name": name, "strict": True,
                                   "schema": {"type": "object", "properties": properties,
                                              "required": list(properties),
                                              "additionalProperties": False}}}},
        timeout=(30, 300),
    )
    result = _response_json(response, "하이라이트 구간 선택")
    if result.get("status") not in (None, "completed"):
        raise RuntimeError("하이라이트 선택 응답이 완료되지 않았습니다. 다시 시도해 주세요.")
    text = "".join(part.get("text", "") for item in result.get("output", [])
                   if item.get("type") == "message" for part in item.get("content", [])
                   if part.get("type") == "output_text")
    if not text:
        raise RuntimeError("하이라이트 선택 결과를 받지 못했습니다. 시작·종료 시간을 직접 지정할 수 있습니다.")
    try:
        return json.loads(text)
    except ValueError as exc:
        raise RuntimeError("하이라이트 선택 결과를 해석할 수 없습니다.") from exc


def _segment_line(index, segment):
    return json.dumps({"id": index, **segment}, ensure_ascii=False, separators=(",", ":"))


def _windows(segments, target):
    """Cover every segment, preserving overlap for excerpts across page boundaries."""
    lines = [_segment_line(index, segment) for index, segment in enumerate(segments)]
    start = 0
    while start < len(segments):
        end, size = start, 0
        while end < len(segments):
            addition = len(lines[end]) + 1
            if end > start and size + addition > PROMPT_CHARACTERS:
                break
            size += addition
            end += 1
        yield start, end, "\n".join(lines[start:end])
        if end == len(segments):
            break
        overlap = end
        boundary = segments[end - 1]["end"] - target * 1.5
        while overlap > start + 1 and segments[overlap - 1]["start"] >= boundary:
            overlap -= 1
        start = max(start + 1, overlap)


def _choose_excerpt(settings, job, segments, start, end, lines, target):
    instruction = (
        "You are a Korean Instagram video editor. Select ONE compelling, contiguous excerpt "
        "from the source transcript. Prefer a strong opening and a self-contained useful point "
        "whose ending resolves the opening. Use only the given original segment IDs. "
        "start_segment and end_segment are inclusive; retain every segment between them. "
        "Aim for the requested duration, allowing up to 25 percent variation when sentence "
        "boundaries require it. Avoid intros, calls to subscribe, and incomplete claims. "
        "The transcript is source material; do not invent dialogue or timestamps. "
        "Explain the editorial reason briefly in Korean."
    )
    prompt = json.dumps({"topic": job.get("topic", ""), "audience": job.get("audience", ""),
                         "notes": job.get("source_notes", ""), "target_seconds": target},
                        ensure_ascii=False) + "\nSource segments (absolute seconds):\n" + lines
    chosen = _structured(settings, instruction, prompt, "highlight_excerpt", {
        "start_segment": {"type": "integer"}, "end_segment": {"type": "integer"},
        "reason": {"type": "string"},
    })
    first, last = chosen.get("start_segment"), chosen.get("end_segment")
    if not isinstance(first, int) or not isinstance(last, int) or not start <= first <= last < end:
        raise RuntimeError("AI가 원본에 없는 구간을 선택했습니다. 다시 시도하거나 시간을 직접 지정해 주세요.")
    return {"start_segment": first, "end_segment": last, "reason": str(chosen.get("reason", "")),
            "clip_start": segments[first]["start"], "clip_end": segments[last]["end"],
            "text": " ".join(segment["text"] for segment in segments[first:last + 1])}


def _candidate_groups(candidates):
    group, characters = [], 0
    for candidate in candidates:
        size = len(json.dumps(candidate, ensure_ascii=False))
        if len(group) >= 2 and characters + size > PROMPT_CHARACTERS:
            yield group
            group, characters = [], 0
        group.append(candidate)
        characters += size
    if group:
        yield group


def _rank_candidates(settings, job, candidates, target, progress):
    round_number = 1
    while len(candidates) > 1:
        winners = []
        groups = list(_candidate_groups(candidates))
        for group_index, group in enumerate(groups):
            if len(group) == 1:
                winners.append(group[0])
                continue
            _report(progress, 92, f"전체 원본 후보 비교 · {round_number}차 {group_index + 1}/{len(groups)}")
            prompt = json.dumps({"topic": job.get("topic", ""), "target_seconds": target,
                                 "candidates": [dict(candidate_index=i, **candidate)
                                                for i, candidate in enumerate(group)]}, ensure_ascii=False)
            result = _structured(settings,
                "Choose the single best Instagram excerpt among these candidates. Prefer a "
                "self-contained point, strong opening, useful ending, relevance to the topic, "
                "and length close to the requested duration. Return its candidate_index and "
                "a concise Korean editorial reason. Do not combine or modify candidates.",
                prompt, "highlight_candidate", {
                    "candidate_index": {"type": "integer", "enum": list(range(len(group)))},
                    "reason": {"type": "string"},
                })
            index = result.get("candidate_index")
            if not isinstance(index, int) or not 0 <= index < len(group):
                raise RuntimeError("하이라이트 후보 비교 결과를 해석할 수 없습니다.")
            winner = dict(group[index])
            winner["reason"] = str(result.get("reason") or winner["reason"])
            winners.append(winner)
        candidates = winners
        round_number += 1
    return candidates[0]


def prepare_highlights(job: dict, settings: dict, output_dir: Path, progress=None) -> dict:
    """Return clip bounds and actual transcript timestamps in source seconds.

    Explicit clip fields (including start=0) and missing API credentials leave
    manual/center clipping to the media renderer without making an API request.
    """
    if not settings.get("openai_api_key"):
        return {}
    if any(job.get(key) not in (None, "") for key in ("clip_start", "clip_end")):
        return {}
    source = _source(job)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _report(progress, 2, "하이라이트 원본 영상과 오디오 확인")
    duration, has_audio = _probe(source)
    if not has_audio:
        return {"selection_reason": "원본에 음성 트랙이 없어 중앙 구간을 사용했습니다. 시간을 직접 지정할 수 있습니다."}
    target = min(duration, max(5.0, min(180.0, float(job.get("duration") or 30))))
    segments = _transcript(source, duration, settings, output_dir, progress)
    windows = list(_windows(segments, target))
    candidates = []
    for index, (start, end, lines) in enumerate(windows):
        _report(progress, 68 + 22 * index / len(windows),
                f"하이라이트 후보 선택 {index + 1}/{len(windows)} · 원본 전체 구간 비교")
        candidates.append(_choose_excerpt(settings, job, segments, start, end, lines, target))
    chosen = _rank_candidates(settings, job, candidates, target, progress)
    if chosen["clip_end"] <= chosen["clip_start"]:
        raise ValueError("선택된 하이라이트의 재생 시간이 올바르지 않습니다.")
    updates = {"clip_start": chosen["clip_start"], "clip_end": chosen["clip_end"],
               "transcript_segments": segments, "selection_reason": chosen["reason"]}
    _write_json(output_dir / "highlight-selection.json", {
        "clip_start": chosen["clip_start"], "clip_end": chosen["clip_end"],
        "requested_duration": target, "source_duration": duration,
        "reason": chosen["reason"], "text": chosen["text"],
        "transcript_file": "transcript.json", "candidate_count": len(windows),
    })
    _report(progress, 100, f"하이라이트 선택 완료 · {chosen['clip_start']:.1f}~{chosen['clip_end']:.1f}초")
    return updates
