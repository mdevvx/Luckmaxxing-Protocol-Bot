import asyncio
from datetime import datetime

import discord
import pytz
from discord import app_commands
from discord.ext import commands, tasks

import config
from content.training import get_content, get_day_title, get_day_video
from database import get_database
from database.base import DatabaseBase
from utils.bot_logger import BotLogger
from utils.logger import logger
from utils.watch_link import build_watch_url
from views.dialogue import DialogueView
from views.dm_ritual import DMRitualView
from views.enrollment import EnrollmentView
from views.graduation import GraduationActionsView
from views.text_card import TextCardView
from views.video_day import VideoDayView

# ──────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────

_EST = pytz.timezone("America/New_York")
_LEGACY_PROTOCOL_CHANNEL_NAMES = {"luxkmaxxing-protocol"}

# Hours (EST) at which daily content is delivered
_NOTIFY_HOURS = {9, 21}  # 9 AM and 9 PM

# How many minutes either side of the target hour counts as "in window"
_WINDOW_MINUTES = 15

# Seconds after delivery before the single inactivity reminder fires
_ALERT_SECONDS = 24 * 3600  # one reminder, ~24h after delivery


# ──────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────


def _in_notify_window() -> bool:
    """
    Return True if the current EST time is within ±WINDOW_MINUTES of a
    target notification hour (9 AM or 9 PM).

    The task loop runs every 30 minutes, so each window is hit exactly
    once per target hour as long as the bot is running.
    """
    now_est = datetime.now(_EST)
    minute_of_day = now_est.hour * 60 + now_est.minute
    for hour in _NOTIFY_HOURS:
        target = hour * 60
        if abs(minute_of_day - target) <= _WINDOW_MINUTES:
            return True
    return False


def _onboarding_view(user: discord.Member) -> TextCardView:
    """Pinned container posted at the top of every private training thread."""
    return TextCardView(
        "Welcome to your Luckmaxxing Training Thread",
        f"Hey {user.mention}, this is your private space for the 8-day program.\n\n"
        "**How it works**\n"
        "• Each day's lesson appears here as an interactive dialogue or video.\n"
        "• Read the **Intern's** message, then click the button to speak your response.\n"
        "• Complete the dialogue to finish the day.\n"
        "• A new day unlocks automatically every 24 hours.\n\n"
        "**This thread is your line** — notifications, offers, and everything else lands "
        "here. Don't close it.\n\n"
        "**Daily mantra** — repeat before sunrise and before any high-risk activity:\n"
        "> *I am lucky. I am the luck.*\n\n"
        "**Warning:** If you don't complete a day's training, you'll get one reminder. "
        "If it still goes unanswered, that day's content reappears the next cycle.\n\n"
        "Gorillions await you.",
        "-# Only you and the bot can see this thread.",
    )


async def _get_training_channel(
    bot: commands.Bot, channel_id: int, guild: discord.Guild | None = None
) -> discord.Thread | None:
    """Resolve a thread ID to a Thread, returning None on any failure."""
    try:
        channel = bot.get_channel(channel_id)
        if channel is None and guild is not None:
            channel = guild.get_thread(channel_id)
        if channel is None:
            channel = await bot.fetch_channel(channel_id)
        return channel  # type: ignore[return-value]
    except Exception as exc:
        logger.warning(f"Could not fetch thread {channel_id}: {exc}")
        return None


def _find_protocol_channel(guild: discord.Guild) -> discord.TextChannel | None:
    valid_names = {config.PROTOCOL_CHANNEL_NAME, *_LEGACY_PROTOCOL_CHANNEL_NAMES}
    return discord.utils.find(
        lambda channel: channel.name in valid_names, guild.text_channels
    )


def _protocol_channel_reference(guild: discord.Guild) -> str:
    channel = _find_protocol_channel(guild)
    return channel.mention if channel else f"#{config.PROTOCOL_CHANNEL_NAME}"


# ──────────────────────────────────────────────────────────────────
#  Cog
# ──────────────────────────────────────────────────────────────────


class ProtocolCog(commands.Cog):
    """Main cog — enrollment, channel creation, dialogue delivery, daily task."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DatabaseBase = get_database()
        self.bot_log = BotLogger(bot, self.db)
        self.send_daily_messages.start()
        self.process_video_watches.start()

    async def cog_load(self):
        await self.db.initialize()
        # Re-register persistent views so buttons survive restarts
        self.bot.add_view(EnrollmentView(on_enroll=self.handle_enrollment))
        self.bot.add_view(DMRitualView(on_confirm=self.handle_dm_ritual))
        logger.info("Protocol cog loaded")

    async def cog_unload(self):
        self.send_daily_messages.cancel()
        self.process_video_watches.cancel()
        await self.db.close()
        logger.info("Protocol cog unloaded")

    async def _remove_onboarding_role(
        self, guild: discord.Guild, user_id: int, reason: str
    ) -> None:
        settings = await self.db.get_guild_settings(guild.id)
        role_id: int | None = settings.get("role_id")
        if not role_id:
            return

        member = guild.get_member(user_id)
        role = guild.get_role(role_id)
        if not member or not role:
            return

        try:
            await member.remove_roles(role, reason=reason)
        except discord.Forbidden:
            logger.warning(f"Missing permission to remove role {role_id}")

    async def _add_staff_to_thread(
        self,
        guild: discord.Guild,
        thread: discord.Thread,
        exclude_id: int,
        team_role_id: int | None,
    ) -> None:
        """
        Add team-role members, administrators, and the guild owner to a
        private training thread so staff can see it without being invited.
        """
        team_role = guild.get_role(team_role_id) if team_role_id else None

        staff: set[discord.Member] = set()
        for member in guild.members:
            if member.id == exclude_id or member.bot:
                continue
            if member.guild_permissions.administrator or member.id == guild.owner_id:
                staff.add(member)
            elif team_role and team_role in member.roles:
                staff.add(member)

        for member in staff:
            try:
                await thread.add_user(member)
            except discord.Forbidden:
                logger.warning(f"Missing permission to add {member.id} to thread {thread.id}")
            except Exception as exc:
                logger.warning(f"Could not add {member.id} to thread {thread.id}: {exc}")

    # ──────────────────────────────────────────
    #  Enrollment handler
    # ──────────────────────────────────────────

    async def handle_enrollment(
        self, interaction: discord.Interaction, enrollment_id: str
    ):
        """
        Called by EnrollmentModal after the user submits their code.
        Verifies the code, sets up the role and private channel, kicks off training.
        """
        guild = interaction.guild
        user = interaction.user
        guild_id = guild.id

        # ── Bot enabled? ──────────────────────────────────────────
        if not await self.db.is_bot_enabled(guild_id):
            await interaction.response.send_message(
                "The Luckmaxxing Protocol is currently disabled in this server.",
                ephemeral=True,
            )
            return

        # ── Already enrolled? ─────────────────────────────────────
        progress = await self.db.get_user_progress(user.id, guild_id)
        if progress:
            channel_id = progress.get("channel_id")
            channel_mention = (
                f"<#{channel_id}>" if channel_id else "your training channel"
            )
            if progress.get("completed"):
                await interaction.response.send_message(
                    "You have already completed the Luckmaxxing Protocol. You are a statistical anomaly.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"You are already enrolled — currently on Day {progress['current_day']}.\n"
                    f"Head to {channel_mention} to continue.",
                    ephemeral=True,
                )
            return

        # ── Defer — enrollment may touch the database and create channels ──
        await interaction.response.defer(ephemeral=True)

        # ── Enroll in DB ──────────────────────────────────────────
        # enroll_user_with_id returns False for an invalid/used ID,
        # and raises an exception for an internal DB error.
        try:
            enrolled = await self.db.enroll_user_with_id(
                user.id, guild_id, enrollment_id
            )
        except Exception as exc:
            logger.error(f"DB error enrolling user {user.id}: {exc}")
            await interaction.followup.send(
                "Enrollment failed due to an internal error. Please try again.",
                ephemeral=True,
            )
            return

        if not enrolled:
            await interaction.followup.send(
                "**Invalid enrollment ID.**\n\n"
                "The code is either not valid for this server, already used, or doesn't exist.\n"
                "Contact an admin if you need a new one.",
                ephemeral=True,
            )
            return

        # ── Guild config (threads channel + role) ─────────────────
        settings = await self.db.get_guild_settings(guild_id)
        threads_channel_id: int | None = settings.get("threads_channel_id")
        role_id: int | None = settings.get("role_id")
        team_role_id: int | None = settings.get("team_role_id")

        # ── Resolve the parent channel threads are created under ──
        parent_channel = (
            guild.get_channel(threads_channel_id) if threads_channel_id else None
        )
        if not isinstance(parent_channel, discord.TextChannel):
            await interaction.followup.send(
                "This server isn't fully configured yet — no threads channel is set. "
                "Ask an admin to run `/configure threads_channel:<channel>`.",
                ephemeral=True,
            )
            await self.db.unenroll_user(user.id, guild_id)
            await self.bot_log.enrollment_failed(
                guild, user, "No threads channel configured"
            )
            return

        # ── Assign enrollment role ────────────────────────────────
        role_assigned = False
        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await user.add_roles(role, reason="Luckmaxxing enrollment")
                    role_assigned = True
                    logger.info(f"Assigned enrollment role {role.name} to {user.id}")
                except discord.Forbidden:
                    logger.warning(f"Missing permission to assign role {role_id}")
            else:
                logger.warning(
                    f"Enrollment role {role_id} not found in guild {guild_id}"
                )

        # ── Create private training thread ─────────────────────────
        safe_name = user.name.lower().replace(" ", "-")[:20]
        channel_name = f"luckmaxx-{safe_name}"

        try:
            channel: discord.Thread = await parent_channel.create_thread(
                name=channel_name,
                type=discord.ChannelType.private_thread,
                invitable=False,
                auto_archive_duration=10080,  # 7 days; daily bot activity keeps it alive
                reason="Luckmaxxing Protocol enrollment",
            )
            await channel.add_user(user)
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to create threads. "
                "Ask an admin to check my permissions.",
                ephemeral=True,
            )
            await self.db.unenroll_user(user.id, guild_id)
            if role_assigned:
                await self._remove_onboarding_role(
                    guild, user.id, reason="Enrollment rollback after thread failure"
                )
            await self.bot_log.enrollment_failed(
                guild, user, "Missing permission to create threads"
            )
            return
        except Exception as exc:
            logger.error(f"Thread creation failed for {user.id}: {exc}")
            await interaction.followup.send(
                "Failed to create your training thread. Please try again.",
                ephemeral=True,
            )
            await self.db.unenroll_user(user.id, guild_id)
            if role_assigned:
                await self._remove_onboarding_role(
                    guild, user.id, reason="Enrollment rollback after thread failure"
                )
            await self.bot_log.enrollment_failed(guild, user, f"Thread creation error: {exc}")
            return

        # ── Persist thread ID ──────────────────────────────────────
        await self.db.save_channel_id(user.id, guild_id, channel.id)

        # ── Invite staff: team role + admins + owner ────────────────
        await self._add_staff_to_thread(
            guild, channel, exclude_id=user.id, team_role_id=team_role_id
        )

        # ── Post pinned onboarding embed + DM ritual ──────────────
        try:
            onboarding_msg = await channel.send(view=_onboarding_view(user))
            await onboarding_msg.pin()
            await channel.send(view=DMRitualView(on_confirm=self.handle_dm_ritual))
        except Exception as exc:
            logger.warning(f"Could not post onboarding messages: {exc}")

        # ── Start Intro + Day 1 ───────────────────────────────────
        await self._send_intro_and_day1(user, guild_id, channel)

        # ── Confirm to the user ───────────────────────────────────
        await interaction.followup.send(
            f"Enrollment successful! Your private training thread: {channel.mention}",
            ephemeral=True,
        )
        await self.bot_log.enrolled(guild, user, enrollment_id, channel)
        logger.info(
            f"User {user.id} enrolled — thread {channel.id} in guild {guild_id}"
        )

    async def handle_dm_ritual(self, interaction: discord.Interaction) -> None:
        """Called by DMRitualView after it successfully DMs the user."""
        if interaction.guild is None:
            return
        await self.db.mark_dm_ack(interaction.user.id, interaction.guild.id)
        logger.info(
            f"User {interaction.user.id} completed DM ritual in guild {interaction.guild.id}"
        )

    # ──────────────────────────────────────────
    #  Content delivery
    # ──────────────────────────────────────────

    async def _send_intro_and_day1(
        self,
        user: discord.Member | discord.User,
        guild_id: int,
        channel: discord.Thread,
    ):
        """Send the Intro dialogue; on completion, immediately send Day 1."""

        intro_content = get_content(0)
        if not intro_content:
            logger.error("Intro content missing")
            return

        async def on_intro_done(_user):
            # Record button click to reset inactivity timer
            await self.db.update_last_button_click(user.id, guild_id)
            await asyncio.sleep(1)  # Brief pause for UX
            await self._send_day(user, guild_id, 1, channel)

        view = DialogueView(
            get_day_title(0),
            intro_content,
            on_complete=on_intro_done,
            user_id=user.id,
            on_button_click=lambda: asyncio.create_task(
                self.db.update_last_button_click(user.id, guild_id)
            ),
        )
        await self._post_container(channel, view)

    async def _advance_day(
        self,
        user: discord.Member | discord.User,
        guild_id: int,
        day: int,
        channel: discord.Thread,
    ) -> None:
        """
        Mark `day` complete for `user` and deliver the next step — either the
        day-complete notice or full graduation. Shared by the dialogue
        on-complete callback and the video-watch confirmation job, since
        both represent the same "day finished" event.
        """
        next_day = day + 1
        await self.db.update_user_day(user.id, guild_id, next_day)
        # Reset inactivity timer on completion
        await self.db.update_last_button_click(user.id, guild_id)

        if day == 1:
            # Day 1 is part of the enrollment session; mark code consumed
            await self.db.mark_enrollment_used(user.id, guild_id)

        guild = channel.guild

        if next_day > config.TOTAL_DAYS:
            await channel.send(
                "**CONGRATULATIONS, GAMBLOR!**\n\n"
                "You have completed the 8-Day Luckmaxxing Protocol.\n"
                "You are no longer average. You are now a **statistical anomaly**.\n\n"
                "Gorillions await you."
            )
            # Swap roles: remove enrollment role, assign completion role
            settings = await self.db.get_guild_settings(guild_id)
            enroll_role_id: int | None = settings.get("role_id")
            completion_role_id: int | None = settings.get("completion_role_id")
            member = guild.get_member(user.id)
            if member:
                if enroll_role_id:
                    enroll_role = guild.get_role(enroll_role_id)
                    if enroll_role:
                        try:
                            await member.remove_roles(
                                enroll_role, reason="Training complete — role swap"
                            )
                        except discord.Forbidden:
                            logger.warning(
                                f"Missing permission to remove enrollment role {enroll_role_id}"
                            )
                if completion_role_id:
                    comp_role = guild.get_role(completion_role_id)
                    if comp_role:
                        try:
                            await member.add_roles(
                                comp_role, reason="Luckmaxxing training complete"
                            )
                            logger.info(
                                f"Assigned completion role {comp_role.name} to {user.id}"
                            )
                        except discord.Forbidden:
                            logger.warning(
                                f"Missing permission to assign completion role {completion_role_id}"
                            )
            grad_view = GraduationActionsView(user)
            await channel.send(view=grad_view)
            await self.bot_log.training_complete(guild, user)
            logger.info(f"User {user.id} completed training in guild {guild_id}")
        else:
            await channel.send(
                f"**Day {day} complete!**\n"
                f"Day {next_day} training will arrive in 24 hours. Keep pushing."
            )
            await self.bot_log.day_complete(guild, user, day)

    async def _send_day(
        self,
        user: discord.Member | discord.User,
        guild_id: int,
        day: int,
        channel: discord.Thread,
    ):
        """
        Post day `day` dialogue to `channel`.
        On completion, advances the DB counter and notifies the user.
        """
        content = get_content(day)
        if not content:
            logger.error(f"No content for day {day}")
            return

        async def on_day_done(_user):
            await self._advance_day(user, guild_id, day, channel)

        video = get_day_video(day)
        if video:
            watch_url, watch_token = build_watch_url(video["url"], day, user.id)
            await self.db.record_watch_token(guild_id, user.id, day, watch_token)
            video_view = VideoDayView(
                get_day_title(day),
                watch_url,
                caption=video.get("caption"),
            )
            await self._post_container(channel, video_view)
        else:
            view = DialogueView(
                get_day_title(day),
                content,
                on_complete=on_day_done,
                user_id=user.id,
                on_button_click=lambda: asyncio.create_task(
                    self.db.update_last_button_click(user.id, guild_id)
                ),
            )
            await self._post_container(channel, view)

    async def send_day_content(
        self,
        user: discord.Member | discord.User,
        guild_id: int,
        day: int,
    ):
        """
        Public entry point used by the daily task.
        Resolves the training channel from DB then calls _send_day.
        """
        progress = await self.db.get_user_progress(user.id, guild_id)
        if not progress:
            logger.warning(f"No progress row for user {user.id} in guild {guild_id}")
            return

        channel_id: int | None = progress.get("channel_id")
        if not channel_id:
            logger.warning(f"No channel_id for user {user.id} in guild {guild_id}")
            return

        guild = self.bot.get_guild(guild_id)
        channel = await _get_training_channel(self.bot, channel_id, guild)
        if channel is None:
            logger.warning(f"Thread {channel_id} not found — skipping user {user.id}")
            return

        await self._send_day(user, guild_id, day, channel)

    @staticmethod
    async def _post_container(
        channel: discord.Thread,
        view: DialogueView | VideoDayView,
    ):
        """Send a day's lesson as a single Components V2 container."""
        msg = await channel.send(view=view)
        view.message = msg

    # ──────────────────────────────────────────
    #  Daily alerts (replaces inactivity boot)
    # ──────────────────────────────────────────

    async def _disable_active_dialogue_button(
        self, channel: discord.Thread
    ) -> None:
        """
        Find the most recent bot message in the channel that has an enabled button
        and replace its view with a fully-disabled version.
        """
        try:
            async for message in channel.history(limit=30):
                if message.author.id != self.bot.user.id:
                    continue
                if not message.components:
                    continue

                for action_row in message.components:
                    for component in action_row.children:
                        if getattr(component, "disabled", True):
                            continue
                        # Rebuild the button as disabled
                        style = getattr(component, "style", discord.ButtonStyle.secondary)
                        if not isinstance(style, discord.ButtonStyle):
                            try:
                                style = discord.ButtonStyle(int(style))
                            except (ValueError, TypeError):
                                style = discord.ButtonStyle.secondary

                        disabled_view = discord.ui.View(timeout=None)
                        btn = discord.ui.Button(
                            label=getattr(component, "label", "...") or "...",
                            style=style,
                            disabled=True,
                        )
                        disabled_view.add_item(btn)
                        await message.edit(
                            content="> Session timed out. Continue when ready.",
                            view=disabled_view,
                        )
                        return
        except Exception as exc:
            logger.warning(
                f"Could not disable dialogue button in channel {channel.id}: {exc}"
            )

    async def _send_alert(self, row: dict) -> None:
        """Send the single reminder for a user who hasn't responded to their day's content."""
        user_id: int = row["user_id"]
        guild_id: int = row["guild_id"]
        day: int = row["current_day"]
        channel_id: int | None = row.get("channel_id")

        # Video days use a link-out button, which never fires an interaction
        # we can see, so last_button_click stays stale even after the user
        # watches. The existence of a video_watches row for this exact day
        # is the real signal they've engaged — the watch job may not have
        # advanced them yet, but a reminder would be wrong either way.
        if get_day_video(day) and await self.db.has_watched_video(user_id, day):
            logger.info(
                f"Skipping reminder for user {user_id} day {day} — video already watched"
            )
            return

        guild = self.bot.get_guild(guild_id)
        if not guild or not channel_id:
            return

        channel = await _get_training_channel(self.bot, channel_id, guild)
        if channel is None:
            return

        await channel.send(
            f"**Reminder, Chief.**\n\n"
            f"Day {day} training is waiting for you. "
            "The dialogue is above — pick up where you left off."
        )
        logger.info(f"Sent reminder for user {user_id} day {day}")
        await self.db.update_alert_count(user_id, guild_id, 1)

    async def _send_daily_alerts(self) -> None:
        """
        Fire a single reminder ~24h after content delivery if the user hasn't
        responded. Skipped once the user clicks any button (last_button_click resets).
        """
        for row in await self.db.get_users_needing_alert(
            min_seconds=_ALERT_SECONDS, alert_count=0
        ):
            try:
                await self._send_alert(row)
            except Exception as exc:
                logger.error(
                    f"Error sending reminder to user {row.get('user_id')}: {exc}",
                    exc_info=True,
                )
            await asyncio.sleep(0.5)

    # ──────────────────────────────────────────
    #  Daily task — runs every 30 minutes
    # ──────────────────────────────────────────

    @tasks.loop(minutes=30)
    async def send_daily_messages(self):
        """
        Every 30 minutes:
        1. For users whose 24-hour window has elapsed: if they responded, deliver the
           next day's content; if not, reset the alert timer without re-posting.
        2. Send a single reminder per cycle to users who haven't responded.
        """
        await self._deliver_daily_content()
        await self._send_daily_alerts()

    async def _deliver_daily_content(self):
        """Send next-day (or same-day retry) training to every user whose 24-hour window has elapsed."""
        enrollments = await self.db.get_all_enrolled_users()
        if not enrollments:
            return

        logger.info(f"Daily delivery — {len(enrollments)} user(s) due")

        for row in enrollments:
            user_id: int = row["user_id"]
            guild_id: int = row["guild_id"]
            day: int = row["current_day"]

            # Days 2–8 are sent here; day 0/1 handled at enrollment
            if day < 2 or day > config.TOTAL_DAYS:
                continue

            if not await self.db.is_bot_enabled(guild_id):
                continue

            try:
                user = await self.bot.fetch_user(user_id)

                progress = await self.db.get_user_progress(user_id, guild_id)

                # If the user hasn't responded since the last delivery, reset the
                # alert timer so reminders cycle again without re-posting training.
                delivered_at = progress.get("last_content_delivered_at") if progress else None
                if delivered_at:
                    try:
                        delivered_dt = datetime.fromisoformat(
                            delivered_at.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                        last_click = progress.get("last_button_click")
                        user_responded = False
                        if last_click:
                            click_dt = datetime.fromisoformat(
                                last_click.replace("Z", "+00:00")
                            ).replace(tzinfo=None)
                            user_responded = click_dt > delivered_dt
                        if not user_responded:
                            await self.db.update_content_delivered(user_id, guild_id)
                            logger.info(
                                f"User {user_id} hasn't responded to day {day} — "
                                "resetting alert timer, skipping re-post"
                            )
                            await asyncio.sleep(0.5)
                            continue
                    except Exception as exc:
                        logger.warning(f"Could not check response state for {user_id}: {exc}")

                # Disable any leftover active button from the previous cycle before
                # posting fresh content so only one dialogue is active at a time.
                if progress and progress.get("channel_id"):
                    ch = await _get_training_channel(
                        self.bot, progress["channel_id"], self.bot.get_guild(guild_id)
                    )
                    if ch:
                        await self._disable_active_dialogue_button(ch)

                await self.send_day_content(user, guild_id, day)

                # Record delivery time and reset alert counter.
                # Deliberately NOT updating last_button_click so alert logic can detect
                # "no user interaction since this delivery".
                await self.db.update_content_delivered(user_id, guild_id)

                guild = self.bot.get_guild(guild_id)
                if guild:
                    await self.bot_log.daily_delivery(guild, user, day)
                logger.info(f"Sent day {day} to user {user_id}")
            except discord.NotFound:
                logger.warning(f"User {user_id} not found — skipping")
            except Exception as exc:
                logger.error(f"Error sending daily content to {user_id}: {exc}", exc_info=True)

            await asyncio.sleep(0.5)  # Be polite to the rate-limiter

        logger.info("Daily delivery complete")

    @send_daily_messages.before_loop
    async def before_daily_loop(self):
        await self.bot.wait_until_ready()

    # ──────────────────────────────────────────
    #  Video watch confirmations — runs every minute
    # ──────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def process_video_watches(self):
        """
        Poll video_watches rows the public /watch page inserted, validate each
        against the token we actually issued in issued_watch_tokens, and
        advance the user's day on a genuine match. Anything that fails
        validation (unknown token, or a token that doesn't match the
        discord_id/day_number it was issued for) is marked processed without
        advancing progress, so a forged submission is inert rather than
        silently ignored forever.
        """
        for row in await self.db.get_pending_video_watches():
            try:
                await self._process_video_watch(row)
            except Exception as exc:
                logger.error(
                    f"Error processing video watch {row.get('id')}: {exc}",
                    exc_info=True,
                )

    @process_video_watches.before_loop
    async def before_process_video_watches(self):
        await self.bot.wait_until_ready()

    async def _process_video_watch(self, row: dict) -> None:
        watch_id = row["id"]
        token = row["token"]
        day_number = row["day_number"]
        discord_id = row["discord_id"]

        issued = await self.db.get_issued_watch_token(token)
        if (
            not issued
            or issued["discord_id"] != discord_id
            or issued["day_number"] != day_number
        ):
            logger.warning(
                f"Rejecting video watch {watch_id} — token doesn't match an "
                f"issued link (token={token!r}, discord_id={discord_id}, day={day_number})"
            )
            await self.db.mark_video_watch_processed(watch_id)
            return

        guild_id = issued["guild_id"]
        progress = await self.db.get_user_progress(discord_id, guild_id)
        if not progress or progress.get("current_day") != day_number:
            # Already advanced past this day (or unenrolled) — stale/duplicate
            # confirmation, nothing left to do.
            await self.db.mark_video_watch_processed(watch_id)
            return

        guild = self.bot.get_guild(guild_id)
        channel = (
            await _get_training_channel(self.bot, progress["channel_id"], guild)
            if progress.get("channel_id")
            else None
        )
        if not guild or not channel:
            logger.warning(
                f"Guild/channel unavailable for video watch {watch_id} — will retry next cycle"
            )
            return  # leave unprocessed so we retry once the cache/thread is available

        member = guild.get_member(discord_id)
        user = member or await self.bot.fetch_user(discord_id)

        await self._advance_day(user, guild_id, day_number, channel)
        await self.db.mark_video_watch_processed(watch_id)
        logger.info(f"Processed video watch {watch_id} — user {discord_id} day {day_number}")

    # ──────────────────────────────────────────
    #  Guards (shared helpers)
    # ──────────────────────────────────────────

    async def _check_enabled(self, interaction: discord.Interaction) -> bool:
        if not await self.db.is_bot_enabled(interaction.guild.id):
            await interaction.response.send_message(
                "The Luckmaxxing Protocol is currently **disabled** in this server.\n"
                "An admin can re-enable it with `/toggle on`.",
                ephemeral=True,
            )
            return False
        return True

    async def _check_configured(self, interaction: discord.Interaction) -> bool:
        settings = await self.db.get_guild_settings(interaction.guild.id)
        threads_channel_id = settings.get("threads_channel_id")
        role_id = settings.get("role_id")
        completion_role_id = settings.get("completion_role_id")

        missing = []
        if not threads_channel_id:
            missing.append(
                "**Threads channel** — where private training threads will be created"
            )
        if not role_id:
            missing.append("**Enrollment role** — assigned to users when they enroll")
        if not completion_role_id:
            missing.append(
                "**Completion role** — assigned to users when they finish training"
            )

        if missing:
            embed = discord.Embed(
                title="Server not configured yet",
                description=(
                    "Before running `/setup` you must configure this server.\n\n"
                    "**Missing:**\n" + "\n".join(f"• {m}" for m in missing) + "\n\n"
                    "**Run this command first:**\n"
                    "```\n/configure role:<role> completion_role:<role> threads_channel:<channel>\n```\n"
                    "All options can be set together or one at a time."
                ),
                color=config.EMBED_COLOR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    # ──────────────────────────────────────────
    #  Slash commands
    # ──────────────────────────────────────────

    @app_commands.command(
        name="setup",
        description="Create the #luckmaxxing-protocol enrollment channel (Admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_protocol(self, interaction: discord.Interaction):
        if not await self._check_enabled(interaction):
            return
        if not await self._check_configured(interaction):
            return

        channel = _find_protocol_channel(interaction.guild)
        if channel and channel.name != config.PROTOCOL_CHANNEL_NAME:
            try:
                await channel.edit(
                    name=config.PROTOCOL_CHANNEL_NAME,
                    reason="Rename legacy protocol channel typo",
                )
            except discord.Forbidden:
                logger.warning(
                    f"Could not rename legacy protocol channel in guild {interaction.guild.id}"
                )

        if not channel:
            try:
                channel = await interaction.guild.create_text_channel(
                    config.PROTOCOL_CHANNEL_NAME,
                    topic="Enroll in the 8-Day Luckmaxxing Protocol",
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "I don't have permission to create channels.", ephemeral=True
                )
                return

        view = EnrollmentView(on_enroll=self.handle_enrollment)
        await channel.send(view=view)

        await interaction.response.send_message(
            f"Setup complete in {channel.mention}.", ephemeral=True
        )
        logger.info(f"Protocol setup in guild {interaction.guild.id}")

    @app_commands.command(
        name="stats", description="View Luckmaxxing Protocol statistics"
    )
    async def view_stats(self, interaction: discord.Interaction):
        if not await self._check_enabled(interaction):
            return

        stats = await self.db.get_stats(interaction.guild.id)
        total = stats["total_enrolled"]
        rate = f"{stats['completed'] / total * 100:.1f}%" if total else "N/A"

        view = TextCardView(
            "Luckmaxxing Protocol — Statistics",
            f"**Enrolled:** {total}\n"
            f"**In Progress:** {stats['in_progress']}\n"
            f"**Completed:** {stats['completed']}\n"
            f"**Completion Rate:** {rate}",
        )
        await interaction.response.send_message(view=view)

    @app_commands.command(name="progress", description="Check your training progress")
    async def check_progress(self, interaction: discord.Interaction):
        if not await self._check_enabled(interaction):
            return

        progress = await self.db.get_user_progress(
            interaction.user.id, interaction.guild.id
        )
        if not progress:
            await interaction.response.send_message(
                "You are not enrolled. Head to the protocol channel to sign up.",
                ephemeral=True,
            )
            return

        day = progress["current_day"]
        done = progress.get("completed", False)
        eid = progress.get("enrollment_id", "N/A")

        if done:
            body = "You have completed the Luckmaxxing Protocol. You are a statistical anomaly."
        else:
            bar = "█" * day + "░" * (config.TOTAL_DAYS - day)
            body = (
                f"**Day:** {day} / {config.TOTAL_DAYS}\n"
                f"**Enrollment ID:** `{eid}`\n"
                f"**Progress:** `{bar}`"
            )

        view = TextCardView(
            "Your Progress",
            body,
            f"-# Enrolled: {progress.get('enrolled_at', 'Unknown')}",
        )
        await interaction.response.send_message(view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProtocolCog(bot))
