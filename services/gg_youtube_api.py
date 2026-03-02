from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from typing import List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request  # <-- needed for refresh


@dataclass
class CaptionTrack:
    id: str
    language: str
    name: str
    is_auto: bool
    is_draft: bool

    @classmethod
    def from_snippet(cls, item: dict) -> "CaptionTrack":
        snip = item["snippet"]
        return cls(
            id=item["id"],
            language=snip.get("language", ""),
            name=snip.get("name", ""),
            is_auto=snip.get("trackKind", "") == "ASR",
            is_draft=bool(snip.get("isDraft", False)),
        )

# ---- Auth & Service -----------------------------------------------------------


SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


class YouTubeAuth:
    def __init__(
        self,
        client_secret_file: str = r"C:\Users\MINH\Desktop\ZaloBot\services\credentials.json",
        token_file: str = "token.json",
        scopes: Optional[List[str]] = None,
    ):
        self.client_secret_file = client_secret_file
        self.token_file = token_file
        self.scopes = scopes or SCOPES

    def get_credentials(self) -> Credentials:
        creds: Optional[Credentials] = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(
                self.token_file, self.scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_file, self.scopes)
                creds = flow.run_local_server(port=0)
            with open(self.token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        return creds

# ---- Helpers: SRT building from transcript segments --------------------------


def _seconds_to_srt_time(s: float) -> str:
    # Convert 12.345 -> "00:00:12,345"
    ms = int(round((s - int(s)) * 1000))
    total = int(s)
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def transcript_segments_to_srt(segments: List[dict]) -> bytes:
    """
    youtube-transcript-api -> SRT bytes
    segments: [{'text': str, 'start': float, 'duration': float}, ...]
    """
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = seg.get("start", 0.0)
        dur = seg.get("duration", 0.0)
        end = start + dur
        text = seg.get("text", "").replace("\r", "")
        lines.append(str(i))
        lines.append(
            f"{_seconds_to_srt_time(start)} --> {_seconds_to_srt_time(end)}")
        lines.append(text)
        lines.append("")  # blank line between cues
    return ("\n".join(lines)).encode("utf-8")

# ---- Main Client --------------------------------------------------------------


class YouTubeCaptionClient:
    """
    - Uses YouTube Data API to LIST tracks for any video.
    - Tries Data API to DOWNLOAD (works only if you OWN the video).
    - On 403 forbidden, falls back to youtube-transcript-api for public transcripts
      and writes SRT locally.
    """

    def __init__(self, credentials: Credentials):
        self.service = build("youtube", "v3", credentials=credentials)

    # -- Listing ----------------------------------------------------------------
    def list_captions(self, video_id: str) -> List[CaptionTrack]:
        try:
            resp = self.service.captions().list(part="snippet", videoId=video_id).execute()
            items = resp.get("items", [])
            return [CaptionTrack.from_snippet(it) for it in items]
        except HttpError as e:
            self._raise_nice_error("listing captions", e)

    def find_caption_by_language(
        self, video_id: str, lang: str, include_auto: bool = True
    ) -> Optional[CaptionTrack]:
        tracks = self.list_captions(video_id)
        candidates = [t for t in tracks if t.language.lower() == lang.lower()]
        if not include_auto:
            candidates = [t for t in candidates if not t.is_auto]
        if candidates:
            return candidates[0]
        prefix_candidates = [
            t for t in tracks if t.language.lower().startswith(lang.lower() + "-")]
        if not include_auto:
            prefix_candidates = [t for t in prefix_candidates if not t.is_auto]
        return prefix_candidates[0] if prefix_candidates else None

    # -- Downloading via Data API ----------------------------------------------
    def download_caption(
        self,
        caption_id: str,
        tfmt: str = "srt",  # or "ttml"
        out_file: Optional[str] = None,
    ) -> bytes:
        if tfmt not in {"srt", "ttml"}:
            raise ValueError("tfmt must be 'srt' or 'ttml'")
        request = self.service.captions().download(id=caption_id, tfmt=tfmt)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        data = buf.getvalue()
        if out_file:
            with open(out_file, "wb") as f:
                f.write(data)
        return data

    def download_caption_by_language(
        self,
        video_id: str,
        lang: str = "en",
        include_auto: bool = True,
        tfmt: str = "srt",
        out_file: Optional[str] = None,
    ) -> Optional[bytes]:
        track = self.find_caption_by_language(video_id, lang, include_auto)
        if not track:
            return None
        return self.download_caption(track.id, tfmt=tfmt, out_file=out_file)

    @staticmethod
    def _raise_nice_error(action: str, e: HttpError) -> None:
        try:
            reason = json.loads(e.content.decode()).get(
                "error", {}).get("message", "")
        except Exception:
            reason = str(e)
        raise RuntimeError(f"Error {action}: {reason}") from e

# ---- Example usage ------------------------------------------------------------


def example():
    VIDEO_ID = "Ftt2q2n5uvY"
    LANG = "en"         # e.g., 'vi' for Vietnamese
    FORMAT = "srt"      # 'srt' or 'ttml'

    auth = YouTubeAuth(client_secret_file="credentials.json",
                       token_file="token.json")
    creds = auth.get_credentials()
    client = YouTubeCaptionClient(creds)

    tracks = client.list_captions(VIDEO_ID)
    print("Caption tracks:")
    for t in tracks:
        print(
            f"- {t.id} | {t.language:<7} | name={t.name!r} | auto={t.is_auto} | draft={t.is_draft}")
    try:
        data = client.download_caption_by_language(
            video_id=VIDEO_ID,
            lang=LANG,
            include_auto=True,
            tfmt=FORMAT,
            out_file=f"{VIDEO_ID}.{LANG}.{FORMAT}",
        )
        if data:
            print(
                f"\n[Data API] Saved: {VIDEO_ID}.{LANG}.{FORMAT} ({len(data)} bytes)")
            return
        else:
            print(
                "\n[Data API] No caption track found in that language; trying fallback...")
    except RuntimeError as e:
        msg = str(e)
        if "forbidden" in msg.lower() or "permissions" in msg.lower():
            print(
                f"\n[Data API] Forbidden for this video (not owned). Using fallback...")
        else:
            # Some other API error
            print(f"\n[Data API] Error: {msg}\nTrying fallback...")


if __name__ == "__main__":
    example()
