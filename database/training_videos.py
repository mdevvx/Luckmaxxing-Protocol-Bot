from datetime import datetime
from typing import Any, Dict, Optional

from supabase import Client, create_client

import config
from utils.logger import logger

# Deliberately independent of database/supabase_db.py's SupabaseDatabase class —
# this is a small, self-contained read path with its own client so training
# video lookups don't depend on that class being initialized.
_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


def get_training_video(day: int) -> Optional[Dict[str, Any]]:
    """Return {"url", "caption"} for the given day's training video, or None if unset."""
    try:
        response = (
            _get_client()
            .table("training_videos")
            .select("url, caption")
            .eq("day_number", day)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error(f"Failed to fetch training video for day {day}: {exc}")
        return None

    rows = response.data or []
    return rows[0] if rows else None


def set_training_video(day: int, url: str, caption: Optional[str] = None) -> bool:
    """Insert or update the training video row for the given day."""
    try:
        _get_client().table("training_videos").upsert(
            {
                "day_number": day,
                "url": url,
                "caption": caption,
                "updated_at": datetime.utcnow().isoformat(),
            },
            on_conflict="day_number",
        ).execute()
        return True
    except Exception as exc:
        logger.error(f"Failed to set training video for day {day}: {exc}")
        return False
