import secrets
from urllib.parse import quote

import config


def build_watch_url(video_url: str, day: int, discord_id: int) -> tuple[str, str]:
    """
    Build the tracked /watch link sent to a user for a given day's video.

    A fresh token is generated on every call (per user, per day, per send).
    Returns (url, token) — the caller is responsible for persisting the
    token via db.record_watch_token() so the watch-processing job can later
    validate that a video_watches row echoes back a token we actually issued,
    instead of trusting whatever the public, login-less /watch page sends.
    """
    token = secrets.token_urlsafe(16)
    url = (
        f"{config.WATCH_BASE_URL}?token={token}&day={day}"
        f"&discord_id={discord_id}&video={quote(video_url, safe='')}"
    )
    return url, token
