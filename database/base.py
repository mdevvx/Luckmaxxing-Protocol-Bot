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
    async def update_alert_count(self, user_id: int, guild_id: int, count: int) -> bool:
        pass

    @abstractmethod
    async def get_users_needing_alert(
        self, min_seconds: int, alert_count: int
    ) -> List[Dict[str, Any]]:
        """Return enrolled users who have had content for min_seconds but not responded."""
        pass
