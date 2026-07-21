import discord
import config
from discord import app_commands
from discord.ext import commands
from typing import Optional

from database import get_database
from database.base import DatabaseBase
from utils.bot_logger import BotLogger
from utils.logger import logger


class AdminCog(commands.Cog):
    """Administrative commands for managing the Luckmaxxing Protocol."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DatabaseBase = get_database()
        self.bot_log = BotLogger(bot, self.db)

    async def cog_load(self):
        await self.db.initialize()
        logger.info("Admin cog loaded")

    async def cog_unload(self):
        await self.db.close()
        logger.info("Admin cog unloaded")

    # ──────────────────────────────────────────
    #  Guard helper
    # ──────────────────────────────────────────

    async def _check_enabled(self, interaction: discord.Interaction) -> bool:
        """
        Return True if the bot is enabled for this guild.
        Sends an ephemeral error and returns False otherwise.

        /toggle intentionally skips this check so admins can
        always re-enable the bot regardless of state.
        /configure also skips it so admins can finish setup before enabling.
        """
        if not await self.db.is_bot_enabled(interaction.guild.id):
            await interaction.response.send_message(
                "The Luckmaxxing Protocol is currently **disabled** in this server.\n"
                "Use `/toggle on` to re-enable it.",
                ephemeral=True,
            )
            return False
        return True

    async def _remove_protocol_roles(
        self, guild: discord.Guild, user_id: int, reason: str
    ) -> None:
        """Remove both enrollment and completion roles from a user (whichever they have)."""
        settings = await self.db.get_guild_settings(guild.id)
        member = guild.get_member(user_id)
        if not member:
            return

        roles_to_remove = []
        for key in ("role_id", "completion_role_id"):
            rid = settings.get(key)
            if rid:
                role = guild.get_role(rid)
                if role and role in member.roles:
                    roles_to_remove.append(role)

        if not roles_to_remove:
            return

        try:
            await member.remove_roles(*roles_to_remove, reason=reason)
        except discord.Forbidden:
            logger.warning(f"Could not remove protocol roles from {user_id}")

    # ──────────────────────────────────────────
    #  /configure
    # ──────────────────────────────────────────

    @app_commands.command(
        name="configure",
        description="Set threads channel, enrollment role, completion role, and log channel (Admin only)",
    )
    @app_commands.describe(
        threads_channel="Channel under which private training threads will be created",
        role="Role assigned to users when they enroll",
        completion_role="Role assigned to users when they finish all training days",
        log_channel="Channel where the bot posts activity logs",
    )
    @app_commands.default_permissions(administrator=True)
    async def configure(
        self,
        interaction: discord.Interaction,
        threads_channel: Optional[discord.TextChannel] = None,
        role: Optional[discord.Role] = None,
        completion_role: Optional[discord.Role] = None,
        log_channel: Optional[discord.TextChannel] = None,
    ):
        """Persist threads channel, roles, and/or log channel for this guild."""
        # /configure is allowed even when disabled so admins can finish setup first
        if (
            threads_channel is None
            and role is None
            and completion_role is None
            and log_channel is None
        ):
            await interaction.response.send_message(
                "Provide at least one option: `threads_channel`, `role`, `completion_role`, or `log_channel`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        success = await self.db.set_guild_config(
            interaction.guild.id,
            threads_channel_id=threads_channel.id if threads_channel else None,
            role_id=role.id if role else None,
            completion_role_id=completion_role.id if completion_role else None,
            log_channel_id=log_channel.id if log_channel else None,
        )

        if not success:
            await interaction.followup.send(
                "Failed to save settings. Please try again.", ephemeral=True
            )
            return

        lines = []
        if threads_channel:
            lines.append(f"**Threads channel:** {threads_channel.mention}")
        if role:
            lines.append(f"**Enrollment role:** {role.mention}")
        if completion_role:
            lines.append(f"**Completion role:** {completion_role.mention}")
        if log_channel:
            lines.append(f"**Log channel:** {log_channel.mention}")

        embed = discord.Embed(
            title="Configuration Updated",
            description="\n".join(lines),
            color=config.EMBED_COLOR,
        )
        embed.add_field(
            name="Next step",
            value="Run `/setup` to post the enrollment message if you haven't already.",
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(
            f"Guild {interaction.guild.id} configured — "
            f"threads_channel={threads_channel.id if threads_channel else None}, "
            f"role={role.id if role else None}, "
            f"completion_role={completion_role.id if completion_role else None}, "
            f"log_channel={log_channel.id if log_channel else None}"
        )

    # ──────────────────────────────────────────
    #  /toggle
    # ──────────────────────────────────────────

    @app_commands.command(
        name="toggle",
        description="Enable or disable the bot for this server (Admin only)",
    )
    @app_commands.describe(state="on to enable, off to disable")
    @app_commands.choices(
        state=[
            app_commands.Choice(name="on", value="on"),
            app_commands.Choice(name="off", value="off"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def toggle_bot(self, interaction: discord.Interaction, state: str):
        enabled = state == "on"
        await interaction.response.defer()
        await self.db.toggle_bot(interaction.guild.id, enabled)

        label = "enabled" if enabled else "disabled"
        embed = discord.Embed(
            title="Bot Status Updated",
            description=f"The Luckmaxxing Protocol is now **{label}** in this server.",
            color=config.EMBED_COLOR if enabled else discord.Color.red(),
        )
        await interaction.followup.send(embed=embed)
        await self.bot_log.bot_toggled(interaction.guild, interaction.user, enabled)
        logger.info(f"Bot {label} for guild {interaction.guild.id}")

    # ──────────────────────────────────────────
    #  /generateid
    # ──────────────────────────────────────────

    @app_commands.command(
        name="generateid",
        description="Generate enrollment codes for members (Admin only)",
    )
    @app_commands.describe(count="How many codes to generate (1–50, default 1)")
    @app_commands.default_permissions(administrator=True)
    async def generate_id(self, interaction: discord.Interaction, count: int = 1):
        if not await self._check_enabled(interaction):
            return
        if not 1 <= count <= 50:
            await interaction.response.send_message(
                "Count must be between 1 and 50.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        ids = await self.db.generate_enrollment_ids(interaction.guild.id, count)

        if not ids:
            await interaction.followup.send(
                "Failed to generate codes. Please try again.", ephemeral=True
            )
            return

        id_list = "\n".join(f"`{c}`" for c in ids)
        embed = discord.Embed(
            title=f"Generated {len(ids)} Enrollment Code(s)",
            color=config.EMBED_COLOR,
        )
        embed.add_field(name="Codes", value=id_list, inline=False)
        embed.add_field(
            name="Instructions",
            value="Share each code with one member. Codes are single-use.",
            inline=False,
        )
        embed.set_footer(text=f"Guild: {interaction.guild.id}")
        await interaction.followup.send(embed=embed, ephemeral=True)
        await self.bot_log.ids_generated(interaction.guild, interaction.user, len(ids))
        logger.info(f"Generated {len(ids)} codes for guild {interaction.guild.id}")

    # ──────────────────────────────────────────
    #  /listids
    # ──────────────────────────────────────────

    @app_commands.command(
        name="listids",
        description="View all unused enrollment codes for this server (Admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def list_ids(self, interaction: discord.Interaction):
        if not await self._check_enabled(interaction):
            return
        await interaction.response.defer()
        unused = await self.db.get_unused_enrollment_ids(interaction.guild.id)

        embed = discord.Embed(title="Unused Enrollment Codes", color=config.EMBED_COLOR)
        if unused:
            embed.description = "\n".join(f"`{c}`" for c in unused)
            embed.set_footer(text=f"{len(unused)} unused code(s)")
        else:
            embed.description = "No unused codes. Use `/generateid` to create some."

        await interaction.followup.send(embed=embed)

    # ──────────────────────────────────────────
    #  /unenroll
    # ──────────────────────────────────────────

    @app_commands.command(
        name="unenroll",
        description="Remove a user from the protocol (Admin only)",
    )
    @app_commands.describe(user="The user to unenroll")
    @app_commands.default_permissions(administrator=True)
    async def unenroll_user(self, interaction: discord.Interaction, user: discord.User):
        if not await self._check_enabled(interaction):
            return
        await interaction.response.defer()

        # Grab channel_id before deleting the row
        progress = await self.db.get_user_progress(user.id, interaction.guild.id)
        channel_id = progress.get("channel_id") if progress else None

        success = await self.db.unenroll_user(user.id, interaction.guild.id)
        if not success:
            await interaction.followup.send(
                f"{user.mention} is not enrolled.", ephemeral=True
            )
            return

        # Optionally delete the training thread
        if channel_id:
            thread = interaction.guild.get_thread(
                channel_id
            ) or interaction.guild.get_channel(channel_id)
            if not thread:
                try:
                    thread = await self.bot.fetch_channel(channel_id)
                except Exception:
                    thread = None
            if thread:
                try:
                    await thread.delete(
                        reason=f"Unenrolled by admin {interaction.user}"
                    )
                except discord.Forbidden:
                    logger.warning(f"Could not delete thread {channel_id}")

        await self._remove_protocol_roles(
            interaction.guild,
            user.id,
            reason=f"Unenrolled by admin {interaction.user}",
        )

        await interaction.followup.send(
            f"{user.mention} has been unenrolled and their training channel removed."
        )
        await self.bot_log.unenrolled(interaction.guild, user, interaction.user)
        logger.info(
            f"Admin unenrolled user {user.id} from guild {interaction.guild.id}"
        )

    # ──────────────────────────────────────────
    #  /globalstats
    # ──────────────────────────────────────────

    @app_commands.command(
        name="globalstats",
        description="View statistics across all servers (Admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def global_stats(self, interaction: discord.Interaction):
        if not await self._check_enabled(interaction):
            return
        await interaction.response.defer()
        stats = await self.db.get_stats()  # No guild_id = global
        total = stats["total_enrolled"]
        rate = f"{stats['completed'] / total * 100:.1f}%" if total else "N/A"

        embed = discord.Embed(
            title="Global Luckmaxxing Protocol Statistics",
            color=config.EMBED_COLOR,
        )
        embed.add_field(name="Total Enrolled", value=total, inline=True)
        embed.add_field(name="In Progress", value=stats["in_progress"], inline=True)
        embed.add_field(name="Completed", value=stats["completed"], inline=True)
        embed.add_field(name="Completion Rate", value=rate, inline=False)
        embed.add_field(name="Servers", value=len(self.bot.guilds), inline=True)
        await interaction.followup.send(embed=embed)

    # ──────────────────────────────────────────
    #  /status
    # ──────────────────────────────────────────

    @app_commands.command(
        name="status", description="Check bot status and configuration (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        if not await self._check_enabled(interaction):
            return
        await interaction.response.defer()
        settings = await self.db.get_guild_settings(interaction.guild.id)

        bot_status = "Enabled" if settings.get("bot_enabled", True) else "Disabled"
        threads_channel_id = settings.get("threads_channel_id")
        role_id = settings.get("role_id")
        completion_role_id = settings.get("completion_role_id")
        log_channel_id = settings.get("log_channel_id")

        threads_channel_label = (
            interaction.guild.get_channel(threads_channel_id).mention
            if threads_channel_id and interaction.guild.get_channel(threads_channel_id)
            else "Not set"
        )
        role_label = (
            interaction.guild.get_role(role_id).name
            if role_id and interaction.guild.get_role(role_id)
            else "Not set"
        )
        completion_role_label = (
            interaction.guild.get_role(completion_role_id).name
            if completion_role_id and interaction.guild.get_role(completion_role_id)
            else "Not set"
        )
        log_label = (
            interaction.guild.get_channel(log_channel_id).mention
            if log_channel_id and interaction.guild.get_channel(log_channel_id)
            else "Not set"
        )

        embed = discord.Embed(title="Bot Status", color=config.EMBED_COLOR)
        embed.add_field(name="Status", value=bot_status, inline=True)
        embed.add_field(
            name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True
        )
        embed.add_field(name="Servers", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Threads Channel", value=threads_channel_label, inline=True)
        embed.add_field(name="Enrollment Role", value=role_label, inline=True)
        embed.add_field(
            name="Completion Role", value=completion_role_label, inline=True
        )
        embed.add_field(name="Log Channel", value=log_label, inline=True)
        embed.set_footer(text=f"Bot ID: {self.bot.user.id}")
        await interaction.followup.send(embed=embed)

    # ──────────────────────────────────────────
    #  $sync  (text command — registers commands to this guild only)
    # ──────────────────────────────────────────

    @commands.command(name="sync")
    async def sync_guild_commands(self, ctx: commands.Context):
        """Register slash commands to the current guild. Reacts ⏳ while working, ✅ when done."""
        if ctx.guild is None:
            return

        app_info = await self.bot.application_info()
        is_owner = ctx.author.id == app_info.owner.id
        is_admin = ctx.author.guild_permissions.administrator
        if not (is_owner or is_admin):
            await ctx.reply("Only the bot owner or a server admin can use this command.")
            return

        try:
            await ctx.message.add_reaction("⏳")
        except discord.Forbidden:
            pass

        try:
            # Register to this guild first (copy_global_to reads from the
            # in-memory global command list, so it must run before we clear it).
            self.bot.tree.copy_global_to(guild=ctx.guild)
            guild_cmds = await self.bot.tree.sync(guild=ctx.guild)

            # Then wipe any stale globally-synced commands so they stop
            # showing up as duplicates alongside the guild-scoped copies.
            self.bot.tree.clear_commands(guild=None)
            await self.bot.tree.sync()

            logger.info(
                f"$sync: registered {len(guild_cmds)} commands to guild {ctx.guild.id}"
            )
        except Exception as exc:
            logger.error(f"sync_guild_commands: {exc}")
            try:
                await ctx.message.remove_reaction("⏳", self.bot.user)
            except discord.Forbidden:
                pass
            try:
                await ctx.message.add_reaction("❌")
            except discord.Forbidden:
                pass
            await ctx.reply(f"Sync failed: {exc}")
            return

        try:
            await ctx.message.remove_reaction("⏳", self.bot.user)
        except discord.Forbidden:
            pass
        try:
            await ctx.message.add_reaction("✅")
        except discord.Forbidden:
            pass
        await ctx.reply(
            f"✅ Synced **{len(guild_cmds)}** command(s) to **{ctx.guild.name}**."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
