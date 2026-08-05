from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DatabaseBase(ABC):
    """Abstract base class defining all database operations for the bot."""

    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    async def generate_enrollment_ids(self, guild_id: int, count: int) -> List[str]:
        pass

    @abstractmethod
    async def get_unused_enrollment_ids(self, guild_id: int) -> List[str]:
        pass

    @abstractmethod
    async def verify_enrollment_id(self, enrollment_id: str, guild_id: int) -> bool:
        pass

    @abstractmethod
    async def enroll_user_with_id(
        self, user_id: int, guild_id: int, enrollment_id: str
    ) -> bool:
        pass

    @abstractmethod
    async def unenroll_user(self, user_id: int, guild_id: int) -> bool:
        """Fully wipe this user's data for this guild: enrollments,
        daily_progress, issued_watch_tokens, and any video_watches rows
        tied to those tokens. video_watches has no guild_id of its own, so
        the wipe is scoped through issued_watch_tokens rather than deleting
        by discord_id alone — otherwise it would also erase watch history
        from other guilds the same user is separately enrolled in."""
        pass

    @abstractmethod
    async def mark_enrollment_used(self, user_id: int, guild_id: int) -> bool:
        pass

    @abstractmethod
    async def mark_dm_ack(self, user_id: int, guild_id: int) -> bool:
        """Record that the user completed the 'report to Papi' DM ritual."""
        pass

    @abstractmethod
    async def get_user_progress(
        self, user_id: int, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def update_user_day(
        self, user_id: int, guild_id: int, current_day: int
    ) -> bool:
        pass

    @abstractmethod
    async def get_all_enrolled_users(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def update_last_button_click(self, user_id: int, guild_id: int) -> bool:
        pass

    @abstractmethod
    async def get_inactive_users(self, seconds: int = 86400) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def save_channel_id(
        self, user_id: int, guild_id: int, channel_id: Optional[int]
    ) -> bool:
        pass

    @abstractmethod
    async def get_enrollment_by_channel(
        self, guild_id: int, channel_id: int
    ) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def toggle_bot(self, guild_id: int, enabled: bool) -> None:
        pass

    @abstractmethod
    async def is_bot_enabled(self, guild_id: int) -> bool:
        pass

    @abstractmethod
    async def set_guild_config(
        self,
        guild_id: int,
        threads_channel_id: Optional[int] = None,
        role_id: Optional[int] = None,
        completion_role_id: Optional[int] = None,
        log_channel_id: Optional[int] = None,
        team_role_id: Optional[int] = None,
    ) -> bool:
        pass

    @abstractmethod
    async def get_stats(self, guild_id: Optional[int] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def update_content_delivered(self, user_id: int, guild_id: int) -> bool:
        """Record that day content was just delivered; resets alert count and delivery timestamp."""
        pass

    @abstractmethod
    async def reset_delivery_window(self, user_id: int, guild_id: int) -> bool:
        """
        Re-arm the daily due-check (last_message_sent) without touching
        last_content_delivered_at, so the 24h alert clock keeps counting
        from the original delivery time.
        """
        pass

    @abstractmethod
    async def update_alert_count(self, user_id: int, guild_id: int, count: int) -> bool:
        pass

    @abstractmethod
    async def get_users_needing_alert(
        self, min_seconds: int, alert_count: int
    ) -> List[Dict[str, Any]]:
        """Return enrolled users who have had content for min_seconds but not responded."""
        pass

    @abstractmethod
    async def get_users_missing_delivery_timestamp(
        self, guild_id: int
    ) -> List[Dict[str, Any]]:
        """Return non-completed enrollments in this guild with no
        last_content_delivered_at set — these can never surface in
        get_users_needing_alert since it has nothing to measure 24h
        against. Used to backfill rows stuck before delivery started
        being stamped for their current step."""
        pass

    @abstractmethod
    async def get_drift_candidates(
        self, guild_id: int, min_seconds: int, alert_count: int
    ) -> List[Dict[str, Any]]:
        """
        Cross-checks daily_progress (an insert-once log, never touched by
        the old alert-timer reset bug) — or enrolled_at for current_day <= 1,
        which has no prior daily_progress row — against
        enrollments.last_content_delivered_at to find users whose real
        overdue time was masked by that bug repeatedly bumping the
        timestamp to "now". Each returned row is augmented with
        '_true_delivered_at'.
        """
        pass

    @abstractmethod
    async def backdate_content_delivered(
        self, user_id: int, guild_id: int, delivered_at: str
    ) -> bool:
        """Correct a drift-affected last_content_delivered_at to its true
        historical value, so future 24h calculations measure from the real
        delivery time instead of the bug's last accidental touch."""
        pass

    @abstractmethod
    async def record_watch_token(
        self, guild_id: int, discord_id: int, day_number: int, token: str
    ) -> bool:
        """Persist a token we issued for a watch link, so it can later be
        validated against what the public /watch page echoes back."""
        pass

    @abstractmethod
    async def get_issued_watch_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Look up the record created when a watch link was issued, to
        validate a video_watches submission against forgery."""
        pass

    @abstractmethod
    async def get_pending_video_watches(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Return unprocessed video_watches rows, oldest first."""
        pass

    @abstractmethod
    async def mark_video_watch_processed(self, watch_id: int) -> bool:
        pass

    @abstractmethod
    async def has_watched_video(
        self, discord_id: int, day_number: int, guild_id: int
    ) -> bool:
        """True if the most recently issued watch token for this user/day/
        guild has a matching video_watches row, regardless of whether the
        watch job has processed it yet. Scoped to the latest issued token
        (a fresh one is issued on every delivery, including after a
        re-enrollment) so a stale watch from this guild's previous cycle,
        or one issued for a different guild entirely (video_watches itself
        has no guild_id), can't falsely count as "watched now". Used by the
        reminder system to detect engagement on video days, since their
        link-out button never fires an interaction we can see."""
        pass
