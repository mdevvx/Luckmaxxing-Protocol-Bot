import secrets
from urllib.parse import quote

import config


def build_watch_url(video_url: str, day: int, discord_id: int) -> str:
    """
    Build the tracked /watch link sent to a user for a given day's video.

    A fresh token is generated on every call (per user, per day, per send) —
    it's opaque to us too; the watch page's job is only to echo it back into
    the video_watches row so it can't be confused with a stale/replayed link.
    """
    token = secrets.token_urlsafe(16)
    return (
        f"{config.WATCH_BASE_URL}?token={token}&day={day}"
        f"&discord_id={discord_id}&video={quote(video_url, safe='')}"
    )
