"""Instagram Reels publishing through Meta's supported Graph API flows.

Facebook Login uses local resumable video upload; Instagram Login uses a
publicly hosted video URL. The caller persists each publish_state snapshot.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import requests


class InstagramError(RuntimeError):
    """An actionable publishing error, preserving whether a result is unknown."""

    def __init__(self, message, *, uncertain=False, code=None):
        super().__init__(message)
        self.uncertain = uncertain
        self.code = code


def _now():
    return datetime.now(timezone.utc).isoformat()


def _configuration(settings):
    token = str(settings.get("instagram_token") or "").strip()
    user_id = str(settings.get("instagram_user_id") or "").strip()
    login = settings.get("instagram_login") or "instagram"
    version = str(settings.get("instagram_api_version") or "v23.0").strip().strip("/")
    if not token or not user_id:
        raise InstagramError("설정에서 Instagram 액세스 토큰과 Instagram 사용자 ID를 입력하세요.")
    if login not in ("instagram", "facebook"):
        raise InstagramError("Instagram 로그인 방식을 instagram 또는 facebook으로 선택하세요.")
    host = "https://graph.instagram.com" if login == "instagram" else "https://graph.facebook.com"
    return token, user_id, login, f"{host}/{version}"


def _request(session, method, url, *, action, **kwargs):
    """Do not retry writes: the persisted workflow decides how to continue."""
    kwargs.setdefault("timeout", (20, 90))
    try:
        response = session.request(method, url, **kwargs)
    except requests.RequestException as exc:
        raise InstagramError(
            f"{action}: 네트워크 연결이 중단되었거나 응답 시간이 초과되었습니다. 저장된 상태에서 다시 시도하세요.",
            uncertain=method.upper() != "GET",
        ) from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise InstagramError(
            f"{action}: Meta 응답을 읽을 수 없습니다(HTTP {response.status_code}).",
            uncertain=method.upper() != "GET",
        ) from exc
    if not isinstance(data, dict):
        raise InstagramError(f"{action}: 예상하지 못한 Meta 응답입니다.", uncertain=method.upper() != "GET")
    error = data.get("error")
    if not response.ok or error:
        error = error if isinstance(error, dict) else {}
        code = error.get("code")
        subcode = error.get("error_subcode")
        detail = error.get("error_user_msg") or error.get("message") or f"HTTP {response.status_code}"
        suffix = f" [코드 {code}, 세부 {subcode}]" if code is not None else ""
        advice = ""
        if code == 190:
            advice = " 설정에서 유효한 토큰으로 갱신한 뒤 다시 시도하세요."
        elif code in (10, 200):
            advice = " 로그인 방식에 맞는 게시 권한, 계정 연결, 앱 접근 수준을 확인하세요."
        elif code in (4, 17, 32, 613) or response.status_code == 429:
            advice = " Meta 사용량 제한입니다. 잠시 후 저장된 작업을 다시 시도하세요."
        raise InstagramError(
            f"{action}: {detail}{suffix}{advice}",
            uncertain=method.upper() != "GET" and (response.status_code >= 500 or bool(error.get("is_transient"))),
            code=code,
        )
    return data


def _caption(job):
    script = job.get("script") or {}
    caption = str(script.get("caption") or "").strip()
    tags = script.get("hashtags") or []
    if isinstance(tags, str):
        tags = tags.split()
    existing = set(caption.split())
    appended = []
    for value in tags:
        tag = "#" + str(value).strip().lstrip("#").replace(" ", "")
        if tag != "#" and tag not in existing:
            appended.append(tag)
            existing.add(tag)
    return "\n\n".join(part for part in (caption, " ".join(appended)) if part)


def _public_video_url(job, settings, video_path):
    explicit = (job.get("artifacts") or {}).get("public_video_url")
    base = str(settings.get("public_base_url") or "").strip().rstrip("/")
    url = str(explicit or "")
    if not url and base:
        url = f"{base}/exports/{quote(str(job['id']), safe='')}/{quote(video_path.name, safe='')}"
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise InstagramError(
            "Instagram Login은 Meta가 내려받을 공개 영상 URL이 필요합니다. 설정의 공개 기본 URL을 입력하거나 "
            "Facebook Login의 로컬 파일 업로드를 사용하세요. 자세한 내용은 INSTAGRAM.md를 확인하세요."
        )
    if parsed.hostname in ("localhost", "127.0.0.1", "::1"):
        raise InstagramError("Meta는 localhost 영상에 접근할 수 없습니다. 공개 HTTPS 미디어 서버의 URL을 입력하세요.")
    return url


class _UploadReader:
    """Stream the existing MP4 and report bytes handed to the HTTP transport."""

    def __init__(self, stream, total, progress):
        self.stream = stream
        self.total = total
        self.progress = progress
        self.last_percent = -1

    def __len__(self):
        return self.total

    def tell(self):
        return self.stream.tell()

    def fileno(self):
        return self.stream.fileno()

    def read(self, amount=-1):
        data = self.stream.read(amount)
        percent = min(55, 20 + int(35 * self.tell() / self.total))
        if percent != self.last_percent:
            self.last_percent = percent
            self.progress(percent, f"Instagram 영상 전송 중 · {self.tell() / 1048576:.1f}/{self.total / 1048576:.1f} MB")
        return data


def connection_status(settings):
    """Read account identity and API quota without creating or publishing media."""
    token, user_id, login, base = _configuration(settings)
    with requests.Session() as session:
        session.headers["Authorization"] = f"Bearer {token}"
        profile = _request(session, "GET", f"{base}/{user_id}", action="계정 확인", params={"fields": "id,username"})
        result = {"connected": True, "login": login, "id": profile.get("id"), "username": profile.get("username")}
        try:
            quota = _request(session, "GET", f"{base}/{user_id}/content_publishing_limit", action="게시 한도 조회", params={"fields": "config,quota_usage"})
            result["publishing_limit"] = quota.get("data", [])
        except InstagramError as exc:
            result["publishing_warning"] = str(exc)
        return result


def publish_reel(job: dict, settings: dict, video_path: Path, progress=None, save_state=None) -> dict:
    """Publish one Reel, resuming persisted container/upload/publish phases.

    A timeout during media_publish leaves publish_unknown. Further calls only
    reconcile that container; they never blindly send another publish request.
    """
    progress = progress or (lambda percent, message: None)
    save_state = save_state or (lambda state: None)
    state = dict(job.get("publish_state") or {})
    token, user_id, login, base = _configuration(settings)
    video_path = Path(video_path)

    def remember(**changes):
        state.update(changes)
        state["updated_at"] = _now()
        save_state(dict(state))

    if state.get("user_id") and (state["user_id"] != user_id or state.get("login") != login):
        raise InstagramError("이 작업은 다른 Instagram 계정 또는 로그인 방식으로 업로드를 시작했습니다. 원래 설정으로 복원하거나 새 작업을 만드세요.")
    # Continue a started container with its original version even after settings change.
    if state.get("api_base"):
        base = state["api_base"]

    with requests.Session() as session:
        session.headers["Authorization"] = f"Bearer {token}"

        def container_status():
            fields = "status_code,status,video_status" if login == "facebook" else "status_code,status"
            result = _request(session, "GET", f"{base}/{state['container_id']}", action="영상 처리 상태 조회", params={"fields": fields})
            remember(container_status=result.get("status_code"), container_detail=result.get("status", ""))
            return result

        def completed():
            media_id = state.get("media_id")
            warning = None
            if media_id and not state.get("permalink"):
                try:
                    media = _request(session, "GET", f"{base}/{media_id}", action="게시 링크 조회", params={"fields": "id,permalink"})
                    remember(permalink=media.get("permalink"))
                except InstagramError as exc:
                    warning = "게시 완료. 링크 조회만 실패했습니다. " + str(exc)
            elif not media_id:
                warning = "Meta에서 게시 완료를 확인했습니다. 이전 응답 유실로 미디어 ID와 링크는 Instagram 프로필에서 확인해야 합니다."
            remember(phase="published", published_at=state.get("published_at") or _now())
            progress(100, warning or "Instagram 릴스 게시 완료")
            return {
                "media_id": media_id,
                "permalink": state.get("permalink"),
                "container_id": state.get("container_id"),
                "published_at": state["published_at"],
                "published": True,
                "warning": warning,
            }

        if state.get("media_id") or state.get("phase") == "published":
            return completed()

        if state.get("phase") in ("publish_inflight", "publish_unknown"):
            progress(92, "이전 게시 요청의 결과 확인 중")
            status = container_status()
            if status.get("status_code") == "PUBLISHED":
                return completed()
            remember(phase="publish_unknown")
            raise InstagramError(
                f"이전 게시 요청의 결과를 확정할 수 없습니다(컨테이너 {state['container_id']}, "
                f"상태 {status.get('status_code', '알 수 없음')}). 게시 요청은 재전송하지 않았습니다. "
                "잠시 후 다시 시도하여 상태를 조회하거나 Instagram 프로필에서 게시 여부를 확인하세요."
            )

        if not state.get("container_id"):
            if not video_path.is_file() or video_path.stat().st_size == 0:
                raise InstagramError("게시할 영상 파일이 없습니다. 먼저 영상을 렌더링하세요.")
            payload = {
                "media_type": "REELS",
                "caption": _caption(job),
                "share_to_feed": "true" if settings.get("share_to_feed", True) else "false",
            }
            if login == "facebook":
                payload["upload_type"] = "resumable"
            else:
                payload["video_url"] = _public_video_url(job, settings, video_path)
            remember(phase="creating", login=login, user_id=user_id, api_base=base, video_size=video_path.stat().st_size, video_name=video_path.name)
            progress(10, "Instagram 영상 컨테이너 생성 중")
            created = _request(session, "POST", f"{base}/{user_id}/media", action="영상 컨테이너 생성", data=payload)
            if not created.get("id"):
                raise InstagramError("Meta가 영상 컨테이너 ID를 반환하지 않았습니다. 다시 시도하세요.")
            remember(
                phase="container_created" if login == "facebook" else "processing",
                container_id=str(created["id"]),
                upload_uri=created.get("uri"),
                container_created_at=_now(),
                video_url=payload.get("video_url"),
            )

        if login == "facebook" and state.get("phase") in ("container_created", "upload_inflight", "upload_unknown"):
            offset = 0
            if state.get("phase") != "container_created":
                status = container_status()
                if status.get("status_code") == "PUBLISHED":
                    return completed()
                if status.get("status_code") == "FINISHED":
                    remember(phase="ready_to_publish")
                elif status.get("status_code") in ("ERROR", "EXPIRED"):
                    raise InstagramError(f"영상 컨테이너를 계속 사용할 수 없습니다: {status.get('status') or status['status_code']}. 새 작업에서 영상을 다시 준비하세요.")
                else:
                    upload = (status.get("video_status") or {}).get("uploading_phase") or {}
                    transferred = upload.get("bytes_transferred")
                    if upload.get("status") == "complete":
                        remember(phase="processing")
                    elif transferred is not None:
                        offset = int(transferred)
                    else:
                        raise InstagramError("이전 영상 전송 상태를 아직 확인할 수 없습니다. 잠시 후 다시 시도하세요. 컨테이너 상태는 저장되어 있습니다.")
            if state.get("phase") not in ("ready_to_publish", "processing"):
                if not video_path.is_file():
                    raise InstagramError("이어 올릴 원본 MP4 파일을 찾을 수 없습니다. 작업의 내보내기 폴더를 복원하세요.")
                total = video_path.stat().st_size
                if total != state.get("video_size") or video_path.name != state.get("video_name"):
                    raise InstagramError("업로드를 시작한 영상과 현재 파일이 다릅니다. 원래 영상을 복원하거나 새 작업을 만드세요.")
                if offset < 0 or offset > total:
                    raise InstagramError("Meta가 반환한 업로드 위치가 영상 크기를 벗어났습니다. 잠시 후 상태를 다시 조회하세요.")
                if offset < total:
                    version = base.rsplit("/", 1)[-1]
                    upload_uri = state.get("upload_uri") or f"https://rupload.facebook.com/ig-api-upload/{version}/{state['container_id']}"
                    remember(phase="upload_inflight", upload_offset=offset)
                    progress(20, "Instagram에 로컬 MP4 업로드 중")
                    try:
                        with video_path.open("rb") as stream:
                            stream.seek(offset)
                            _request(
                                session, "POST", upload_uri, action="로컬 영상 업로드",
                                data=_UploadReader(stream, total, progress),
                                headers={"Authorization": f"OAuth {token}", "offset": str(offset), "file_size": str(total), "Content-Length": str(total - offset), "Content-Type": "application/octet-stream"},
                                timeout=(20, 600),
                            )
                    except InstagramError:
                        remember(phase="upload_unknown")
                        raise
                remember(phase="processing", upload_offset=total)

        deadline = time.monotonic() + 300
        while True:
            status = container_status()
            code = status.get("status_code")
            if code == "PUBLISHED":
                return completed()
            if code == "FINISHED":
                remember(phase="ready_to_publish")
                break
            if code in ("ERROR", "EXPIRED"):
                remember(phase="container_failed")
                raise InstagramError(f"Instagram 영상 처리 실패: {status.get('status') or code}. 영상 형식과 공개 URL 접근 여부를 확인하고 새 작업에서 다시 준비하세요.")
            progress(75, f"Instagram 영상 처리 중 · {code or '대기'}")
            if time.monotonic() >= deadline:
                raise InstagramError("Instagram 영상 처리가 아직 끝나지 않았습니다. 컨테이너를 저장했으며 다시 시도하면 처리 상태부터 이어갑니다.")
            time.sleep(10)

        progress(92, "Instagram 릴스 게시 중")
        remember(phase="publish_inflight", publish_requested_at=_now())
        try:
            published = _request(session, "POST", f"{base}/{user_id}/media_publish", action="릴스 게시", data={"creation_id": state["container_id"]})
        except InstagramError as exc:
            remember(phase="publish_unknown" if exc.uncertain else "ready_to_publish")
            raise
        if not published.get("id"):
            remember(phase="publish_unknown")
            raise InstagramError("게시 응답에 미디어 ID가 없습니다. 게시 결과를 확인하려면 다시 시도하세요. 같은 게시 요청은 자동 재전송하지 않습니다.")
        remember(phase="published", media_id=str(published["id"]), published_at=_now())
        return completed()
