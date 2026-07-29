import secrets
import string
from datetime import datetime
from typing import Any, Dict, List, Optional

from supabase import create_client, Client

import config
from database.base import DatabaseBase
from utils.logger import logger


class SupabaseDatabase(DatabaseBase):
    """Concrete Supabase implementation of DatabaseBase."""

    def __init__(self):
        self.client: Optional[Client] = None
        self._initialized = False

        try:
            self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            self._initialized = True
            logger.info("Supabase client created in __init__")
        except Exception as exc:
            logger.error(f"Failed to create Supabase client in __init__: {exc}")

    # ─────────────────────────────────────────────
    #  Internal helpers
    # ─────────────────────────────────────────────

    def _get_client(self) -> Client:
        if self.client is None:
            logger.warning("Supabase client is None – recreating...")
            self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        return self.client

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()

    def _release_enrollment_id(
        self, enrollment_id: str, guild_id: int, user_id: int
    ) -> None:
        """Release an unconsumed code if it is still claimed by this user."""
        self._get_client().table("enrollment_ids").update(
            {"used": False, "used_by": None, "used_at": None}
        ).eq("id_code", enrollment_id).eq("guild_id", guild_id).eq(
            "used_by", user_id
        ).execute()

    # ─────────────────────────────────────────────
    #  Lifecycle
    # ─────────────────────────────────────────────

    async def initialize(self) -> None:
        if self._initialized:
            return
        try:
            if self.client is None:
                self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            self._get_client().table("enrollments").select("*").limit(1).execute()
            self._initialized = True
            logger.info("Supabase connection verified")
        except Exception as exc:
            self._initialized = False
            self.client = None
            logger.error(f"Supabase initialization failed: {exc}")
            raise

    async def close(self) -> None:
        if not self._initialized:
            return
        self._initialized = False
        self.client = None
        logger.info("Supabase connection closed")

    # ─────────────────────────────────────────────
    #  Enrollment IDs
    # ─────────────────────────────────────────────

    async def generate_enrollment_ids(self, guild_id: int, count: int) -> List[str]:
        client = self._get_client()
        generated: List[str] = []
        attempts = 0

        while len(generated) < count and attempts < count * 3:
            attempts += 1
            code = "".join(
                secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5)
            )
            try:
                client.table("enrollment_ids").insert(
                    {
                        "id_code": code,
                        "guild_id": guild_id,
                        "used": False,
                        "created_at": self._now(),
                    }
                ).execute()
                generated.append(code)
                logger.info(f"Generated enrollment ID {code} for guild {guild_id}")
            except Exception as exc:
                msg = str(exc).lower()
                if "duplicate" in msg or "unique" in msg:
                    continue
                logger.error(f"Error inserting enrollment ID {code}: {exc}")

        return generated

    async def get_unused_enrollment_ids(self, guild_id: int) -> List[str]:
        try:
            resp = (
                self._get_client()
                .table("enrollment_ids")
                .select("id_code")
                .eq("guild_id", guild_id)
                .eq("used", False)
                .order("created_at", desc=True)
                .execute()
            )
            return [row["id_code"] for row in (resp.data or [])]
        except Exception as exc:
            logger.error(f"get_unused_enrollment_ids: {exc}")
            return []

    async def verify_enrollment_id(self, enrollment_id: str, guild_id: int) -> bool:
        try:
            resp = (
                self._get_client()
                .table("enrollment_ids")
                .select("id_code")
                .eq("id_code", enrollment_id)
                .eq("guild_id", guild_id)
                .eq("used", False)
                .execute()
            )
            valid = bool(resp.data)
            if not valid:
                logger.warning(
                    f"Invalid/used enrollment ID {enrollment_id} for guild {guild_id}"
                )
            return valid
        except Exception as exc:
            logger.error(f"verify_enrollment_id: {exc}")
            return False

    # ─────────────────────────────────────────────
    #  User Enrollment
    # ─────────────────────────────────────────────

    async def enroll_user_with_id(
        self, user_id: int, guild_id: int, enrollment_id: str
    ) -> bool:
        client = self._get_client()
        now = self._now()

        # Step 1: Atomically claim the enrollment ID.
        # Returns False (not an exception) if the ID is invalid, used, or wrong guild.
        try:
            claim_resp = (
                client.table("enrollment_ids")
                .update({"used": True, "used_by": user_id, "used_at": now})
                .eq("id_code", enrollment_id)
                .eq("guild_id", guild_id)
                .eq("used", False)
                .execute()
            )
        except Exception as exc:
            logger.error(f"enroll_user_with_id claim step: {exc}")
            return False

        if not claim_resp.data:
            logger.warning(
                f"Enrollment ID {enrollment_id} not found / already used for guild {guild_id}"
            )
            return False

        # Step 2: Create the enrollment row.
        # On failure, release the claimed ID and re-raise so the caller can show
        # a "DB error, try again" message rather than "invalid ID".
        try:
            client.table("enrollments").insert(
                {
                    "user_id": user_id,
                    "guild_id": guild_id,
                    "enrollment_id": enrollment_id,
                    "enrollment_used": False,
                    "current_day": 0,
                    "channel_id": None,
                    "enrolled_at": now,
                    "last_button_click": now,
                }
            ).execute()
            logger.info(f"User {user_id} enrolled in guild {guild_id}")
            return True
        except Exception as exc:
            try:
                self._release_enrollment_id(enrollment_id, guild_id, user_id)
            except Exception as release_exc:
                logger.warning(
                    f"Could not release enrollment ID {enrollment_id}: {release_exc}"
                )
            msg = str(exc).lower()
            if "duplicate" in msg or "unique" in msg:
                logger.warning(f"User {user_id} already enrolled in guild {guild_id}")
            else:
                logger.error(f"enroll_user_with_id insert step: {exc}")
            raise

    async def unenroll_user(self, user_id: int, guild_id: int) -> bool:
        client = self._get_client()
        try:
            row = await self.get_user_progress(user_id, guild_id)
            if not row:
                return False

            enrollment_id = row.get("enrollment_id")
            enrollment_used = row.get("enrollment_used", False)

            try:
                client.table("daily_progress").delete().eq("user_id", user_id).eq(
                    "guild_id", guild_id
                ).execute()
            except Exception as exc:
                logger.warning(f"Could not delete daily_progress: {exc}")

            client.table("enrollments").delete().eq("user_id", user_id).eq(
                "guild_id", guild_id
            ).execute()

            if enrollment_id and not enrollment_used:
                try:
                    self._release_enrollment_id(enrollment_id, guild_id, user_id)
                except Exception as exc:
                    logger.warning(f"Could not free enrollment ID: {exc}")

            logger.info(f"User {user_id} unenrolled from guild {guild_id}")
            return True
        except Exception as exc:
            logger.error(f"unenroll_user: {exc}")
            return False

    async def mark_enrollment_used(self, user_id: int, guild_id: int) -> bool:
        try:
            self._get_client().table("enrollments").update(
                {"enrollment_used": True}
            ).eq("user_id", user_id).eq("guild_id", guild_id).execute()
            return True
        except Exception as exc:
            logger.error(f"mark_enrollment_used: {exc}")
            return False

    async def mark_dm_ack(self, user_id: int, guild_id: int) -> bool:
        try:
            self._get_client().table("enrollments").update(
                {"dm_ack": True}
            ).eq("user_id", user_id).eq("guild_id", guild_id).execute()
            return True
        except Exception as exc:
            logger.error(f"mark_dm_ack: {exc}")
            return False

    # ─────────────────────────────────────────────
    #  Progress Tracking
    # ─────────────────────────────────────────────

    async def get_user_progress(
        self, user_id: int, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        try:
            resp = (
                self._get_client()
                .table("enrollments")
                .select("*")
                .eq("user_id", user_id)
                .eq("guild_id", guild_id)
                .execute()
            )
            return resp.data[0] if resp.data else None
        except Exception as exc:
            logger.error(f"get_user_progress: {exc}")
            return None

    async def update_user_day(
        self, user_id: int, guild_id: int, current_day: int
    ) -> bool:
        client = self._get_client()
        try:
            completed_day = max(1, min(current_day - 1, config.TOTAL_DAYS))
            client.table("enrollments").update(
                {
                    "current_day": current_day,
                    "last_message_sent": self._now(),
                    "completed": current_day > config.TOTAL_DAYS,
                }
            ).eq("user_id", user_id).eq("guild_id", guild_id).execute()

            try:
                client.table("daily_progress").insert(
                    {
                        "user_id": user_id,
                        "guild_id": guild_id,
                        "day_number": completed_day,
                        "completed_at": self._now(),
                    }
                ).execute()
            except Exception as exc:
                logger.warning(f"Could not log daily_progress: {exc}")

            return True
        except Exception as exc:
            logger.error(f"update_user_day: {exc}")
            return False

    async def update_last_button_click(self, user_id: int, guild_id: int) -> bool:
        """
        Stamp the current UTC time as last_button_click.
        Called on every button interaction and on day completion
        to reset the 24-hour inactivity window.
        """
        try:
            self._get_client().table("enrollments").update(
                {"last_button_click": self._now()}
            ).eq("user_id", user_id).eq("guild_id", guild_id).execute()
            return True
        except Exception as exc:
            logger.error(f"update_last_button_click: {exc}")
            return False

    async def get_inactive_users(self, seconds: int = 86400) -> List[Dict[str, Any]]:
        """
        Return enrollments where last_button_click is older than `seconds` ago
        (or NULL, meaning the user never clicked anything).
        Only returns non-completed enrollments.
        """
        try:
            resp = (
                self._get_client()
                .table("enrollments")
                .select("*")
                .eq("completed", False)
                .execute()
            )

            result = []
            now = datetime.utcnow()

            for row in resp.data or []:
                last_click = row.get("last_button_click")
                if not last_click:
                    # Never clicked — check against enrolled_at instead
                    enrolled_at = row.get("enrolled_at")
                    if enrolled_at:
                        try:
                            enrolled_dt = datetime.fromisoformat(
                                enrolled_at.replace("Z", "+00:00")
                            ).replace(tzinfo=None)
                            if (now - enrolled_dt).total_seconds() >= seconds:
                                result.append(row)
                        except Exception:
                            result.append(row)
                    continue

                try:
                    click_dt = datetime.fromisoformat(
                        last_click.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    if (now - click_dt).total_seconds() >= seconds:
                        result.append(row)
                except Exception:
                    result.append(row)

            return result
        except Exception as exc:
            logger.error(f"get_inactive_users: {exc}")
            return []

    async def get_all_enrolled_users(self) -> List[Dict[str, Any]]:
        """
        Returns enrollments where the next daily message is due
        (not completed, past the intro, last sent >= 24 h ago or never).
        """
        try:
            resp = (
                self._get_client()
                .table("enrollments")
                .select("*")
                .eq("completed", False)
                .gt("current_day", 1)
                .execute()
            )

            result = []
            now = datetime.utcnow()

            for row in resp.data or []:
                last_sent = row.get("last_message_sent")
                if not last_sent:
                    result.append(row)
                    continue
                try:
                    last_dt = datetime.fromisoformat(
                        last_sent.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    if (now - last_dt).total_seconds() >= 86400:
                        result.append(row)
                except Exception:
                    result.append(row)

            return result
        except Exception as exc:
            logger.error(f"get_all_enrolled_users: {exc}")
            return []

    async def update_content_delivered(self, user_id: int, guild_id: int) -> bool:
        """
        Called when a day's dialogue is freshly delivered.
        Sets last_content_delivered_at + last_message_sent to now and resets daily_alert_count.
        Does NOT touch last_button_click so alerts can detect "no user response since delivery".
        """
        try:
            now = self._now()
            self._get_client().table("enrollments").update(
                {
                    "last_content_delivered_at": now,
                    "last_message_sent": now,
                    "daily_alert_count": 0,
                }
            ).eq("user_id", user_id).eq("guild_id", guild_id).execute()
            return True
        except Exception as exc:
            logger.error(f"update_content_delivered: {exc}")
            return False

    async def update_alert_count(self, user_id: int, guild_id: int, count: int) -> bool:
        try:
            self._get_client().table("enrollments").update(
                {"daily_alert_count": count}
            ).eq("user_id", user_id).eq("guild_id", guild_id).execute()
            return True
        except Exception as exc:
            logger.error(f"update_alert_count: {exc}")
            return False

    async def get_users_needing_alert(
        self, min_seconds: int, alert_count: int
    ) -> List[Dict[str, Any]]:
        """
        Return non-completed users whose:
        - daily_alert_count == alert_count  (hasn't had this alert yet)
        - last_content_delivered_at >= min_seconds ago
        - last_button_click is NULL or before last_content_delivered_at
          (user hasn't responded since delivery)

        Not filtered by current_day: Day 1 sits at current_day == 0 until it's
        completed (see update_user_day), so day-1 stragglers need to be caught
        here too, not just day 2-8 ones.
        """
        try:
            resp = (
                self._get_client()
                .table("enrollments")
                .select("*")
                .eq("completed", False)
                .eq("daily_alert_count", alert_count)
                .execute()
            )

            result = []
            now = datetime.utcnow()

            for row in resp.data or []:
                delivered_at = row.get("last_content_delivered_at")
                if not delivered_at:
                    continue

                try:
                    delivered_dt = datetime.fromisoformat(
                        delivered_at.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except Exception:
                    continue

                if (now - delivered_dt).total_seconds() < min_seconds:
                    continue

                # Skip if user has clicked a button after delivery
                last_click = row.get("last_button_click")
                if last_click:
                    try:
                        click_dt = datetime.fromisoformat(
                            last_click.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                        if click_dt > delivered_dt:
                            continue
                    except Exception:
                        pass

                result.append(row)

            return result
        except Exception as exc:
            logger.error(f"get_users_needing_alert: {exc}")
            return []

    async def get_users_missing_delivery_timestamp(
        self, guild_id: int
    ) -> List[Dict[str, Any]]:
        try:
            resp = (
                self._get_client()
                .table("enrollments")
                .select("*")
                .eq("guild_id", guild_id)
                .eq("completed", False)
                .is_("last_content_delivered_at", "null")
                .execute()
            )
            return resp.data or []
        except Exception as exc:
            logger.error(f"get_users_missing_delivery_timestamp: {exc}")
            return []

    async def get_enrollment_by_channel(
        self, guild_id: int, channel_id: int
    ) -> Optional[Dict[str, Any]]:
        try:
            resp = (
                self._get_client()
                .table("enrollments")
                .select("*")
                .eq("guild_id", guild_id)
                .eq("channel_id", channel_id)
                .execute()
            )
            return resp.data[0] if resp.data else None
        except Exception as exc:
            logger.error(f"get_enrollment_by_channel: {exc}")
            return None

    # ─────────────────────────────────────────────
    #  Channel management
    # ─────────────────────────────────────────────

    async def save_channel_id(
        self, user_id: int, guild_id: int, channel_id: Optional[int]
    ) -> bool:
        try:
            self._get_client().table("enrollments").update(
                {"channel_id": channel_id}
            ).eq("user_id", user_id).eq("guild_id", guild_id).execute()
            logger.info(
                f"Saved channel {channel_id} for user {user_id} in guild {guild_id}"
            )
            return True
        except Exception as exc:
            logger.error(f"save_channel_id: {exc}")
            return False

    # ─────────────────────────────────────────────
    #  Guild Settings
    # ─────────────────────────────────────────────

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        client = self._get_client()
        try:
            resp = (
                client.table("guild_settings")
                .select("*")
                .eq("guild_id", guild_id)
                .execute()
            )
            if resp.data:
                return resp.data[0]

            defaults: Dict[str, Any] = {
                "guild_id": guild_id,
                "bot_enabled": True,
                "threads_channel_id": None,
                "role_id": None,
                "completion_role_id": None,
                "team_role_id": None,
                "created_at": self._now(),
            }
            try:
                client.table("guild_settings").insert(defaults).execute()
            except Exception as exc:
                logger.warning(f"Could not insert default guild_settings: {exc}")
            return defaults
        except Exception as exc:
            logger.error(f"get_guild_settings: {exc}")
            return {"guild_id": guild_id, "bot_enabled": True}

    async def toggle_bot(self, guild_id: int, enabled: bool) -> None:
        try:
            self._get_client().table("guild_settings").upsert(
                {
                    "guild_id": guild_id,
                    "bot_enabled": enabled,
                    "updated_at": self._now(),
                }
            ).execute()
        except Exception as exc:
            logger.error(f"toggle_bot: {exc}")

    async def is_bot_enabled(self, guild_id: int) -> bool:
        settings = await self.get_guild_settings(guild_id)
        return settings.get("bot_enabled", True)

    async def set_guild_config(
        self,
        guild_id: int,
        threads_channel_id: Optional[int] = None,
        role_id: Optional[int] = None,
        completion_role_id: Optional[int] = None,
        log_channel_id: Optional[int] = None,
        team_role_id: Optional[int] = None,
    ) -> bool:
        try:
            payload: Dict[str, Any] = {
                "guild_id": guild_id,
                "updated_at": self._now(),
            }
            if threads_channel_id is not None:
                payload["threads_channel_id"] = threads_channel_id
            if role_id is not None:
                payload["role_id"] = role_id
            if completion_role_id is not None:
                payload["completion_role_id"] = completion_role_id
            if log_channel_id is not None:
                payload["log_channel_id"] = log_channel_id
            if team_role_id is not None:
                payload["team_role_id"] = team_role_id

            self._get_client().table("guild_settings").upsert(payload).execute()
            logger.info(f"Guild config updated for {guild_id}: {payload}")
            return True
        except Exception as exc:
            logger.error(f"set_guild_config: {exc}")
            return False

    # ─────────────────────────────────────────────
    #  Statistics
    # ─────────────────────────────────────────────

    async def get_stats(self, guild_id: Optional[int] = None) -> Dict[str, Any]:
        client = self._get_client()
        try:

            def _build(eq_completed: bool):
                q = (
                    client.table("enrollments")
                    .select("*", count="exact")
                    .eq("completed", eq_completed)
                )
                if guild_id:
                    q = q.eq("guild_id", guild_id)
                return q.execute()

            total_resp = client.table("enrollments").select("*", count="exact")
            if guild_id:
                total_resp = total_resp.eq("guild_id", guild_id)
            total_resp = total_resp.execute()

            done_resp = _build(True)

            total = (
                total_resp.count
                if hasattr(total_resp, "count")
                else len(total_resp.data or [])
            )
            done = (
                done_resp.count
                if hasattr(done_resp, "count")
                else len(done_resp.data or [])
            )

            return {
                "total_enrolled": total,
                "completed": done,
                "in_progress": total - done,
            }
        except Exception as exc:
            logger.error(f"get_stats: {exc}")
            return {"total_enrolled": 0, "completed": 0, "in_progress": 0}

    # ─────────────────────────────────────────────
    #  Watch tokens
    # ─────────────────────────────────────────────

    async def record_watch_token(
        self, guild_id: int, discord_id: int, day_number: int, token: str
    ) -> bool:
        try:
            self._get_client().table("issued_watch_tokens").insert(
                {
                    "token": token,
                    "guild_id": guild_id,
                    "discord_id": discord_id,
                    "day_number": day_number,
                    "created_at": self._now(),
                }
            ).execute()
            return True
        except Exception as exc:
            logger.error(f"record_watch_token: {exc}")
            return False

    async def get_issued_watch_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            resp = (
                self._get_client()
                .table("issued_watch_tokens")
                .select("*")
                .eq("token", token)
                .limit(1)
                .execute()
            )
            return resp.data[0] if resp.data else None
        except Exception as exc:
            logger.error(f"get_issued_watch_token: {exc}")
            return None

    async def get_pending_video_watches(self, limit: int = 25) -> List[Dict[str, Any]]:
        try:
            resp = (
                self._get_client()
                .table("video_watches")
                .select("*")
                .eq("processed", False)
                .order("created_at")
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception as exc:
            logger.error(f"get_pending_video_watches: {exc}")
            return []

    async def mark_video_watch_processed(self, watch_id: int) -> bool:
        try:
            self._get_client().table("video_watches").update(
                {"processed": True}
            ).eq("id", watch_id).execute()
            return True
        except Exception as exc:
            logger.error(f"mark_video_watch_processed: {exc}")
            return False

    async def has_watched_video(self, discord_id: int, day_number: int) -> bool:
        try:
            resp = (
                self._get_client()
                .table("video_watches")
                .select("id")
                .eq("discord_id", discord_id)
                .eq("day_number", day_number)
                .limit(1)
                .execute()
            )
            return bool(resp.data)
        except Exception as exc:
            logger.error(f"has_watched_video: {exc}")
            return False
