from typing import Optional, Union

import discord

import config
from database.base import DatabaseBase
from utils.logger import logger

_CLOSE_BUTTON_ID = "graduation_close_channel"
_KEEP_OPEN_BUTTON_ID = "graduation_keep_open"


class GraduationActionsView(discord.ui.LayoutView):
    """Persistent Components V2 container for the final post-training channel decision."""

    def __init__(
        self,
        db: DatabaseBase,
        user: Optional[Union[discord.Member, discord.User]] = None,
        *,
        questions_enabled: bool = False,
    ):
        super().__init__(timeout=None)
        self.db = db

        self._close_button = discord.ui.Button(
            label="Chief, me ready use powers.",
            style=discord.ButtonStyle.danger,
            custom_id=_CLOSE_BUTTON_ID,
        )
        self._close_button.callback = self.close_channel

        self._keep_open_button = discord.ui.Button(
            label="Chief, me have question / feedback.",
            style=discord.ButtonStyle.success,
            custom_id=_KEEP_OPEN_BUTTON_ID,
            disabled=questions_enabled,
        )
        self._keep_open_button.callback = self.keep_open

        mention = user.mention if user else "Gamblor"
        children = [
            discord.ui.TextDisplay("## Luckmaxxing Protocol Complete"),
            discord.ui.TextDisplay(
                f"{mention}, you finished the 8-Day Luckmaxxing Protocol.\n\n"
                f"You are now a **{config.GRADUATE_ROLE_NAME}** and a **statistical anomaly**.\n\n"
                "Use the buttons below to close this channel or keep it open for questions or feedback."
            ),
        ]

        if questions_enabled:
            children.append(discord.ui.Separator())
            children.append(
                discord.ui.TextDisplay(
                    "**Questions unlocked**\n"
                    "You can type in this channel now. Close it any time with the red button."
                )
            )
            children.append(
                discord.ui.TextDisplay(
                    "-# Badge unlocked. Questions and feedback are enabled."
                )
            )
        else:
            children.append(
                discord.ui.TextDisplay(
                    "-# Badge unlocked. Choose what happens to this channel next."
                )
            )

        children.append(
            discord.ui.ActionRow(self._close_button, self._keep_open_button)
        )

        self.add_item(discord.ui.Container(*children, accent_colour=config.EMBED_COLOR))

    async def _resolve_context(
        self, interaction: discord.Interaction
    ) -> tuple[Optional[dict], Optional[discord.TextChannel]]:
        channel = interaction.channel
        guild = interaction.guild

        if guild is None or not isinstance(channel, discord.TextChannel):
            return None, None

        progress = await self.db.get_enrollment_by_channel(guild.id, channel.id)
        if not progress:
            return None, channel

        return progress, channel

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        progress, _channel = await self._resolve_context(interaction)
        if not progress:
            await interaction.response.send_message(
                "This completion action is no longer available.",
                ephemeral=True,
            )
            return False

        if not progress.get("completed"):
            await interaction.response.send_message(
                "This action unlocks after training is complete.",
                ephemeral=True,
            )
            return False

        if interaction.user.id != progress["user_id"]:
            await interaction.response.send_message(
                "This is not your completion badge.",
                ephemeral=True,
            )
            return False

        return True

    async def close_channel(self, interaction: discord.Interaction) -> None:
        progress, channel = await self._resolve_context(interaction)
        if not progress or channel is None:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "This channel is already gone.",
                    ephemeral=True,
                )
            return

        await interaction.response.send_message(
            "Closing this channel.",
            ephemeral=True,
        )

        try:
            await self.db.save_channel_id(
                progress["user_id"], progress["guild_id"], None
            )
            await channel.delete(reason="Graduate chose to close their channel")
        except discord.Forbidden:
            logger.warning(f"Missing permission to delete completed channel {channel.id}")
            await interaction.followup.send(
                "I could not close this channel. Ask an admin to check my permissions.",
                ephemeral=True,
            )
        except Exception as exc:
            logger.error(f"GraduationActionsView.close_channel: {exc}")
            await interaction.followup.send(
                "Something went wrong while closing this channel.",
                ephemeral=True,
            )

    async def keep_open(self, interaction: discord.Interaction) -> None:
        progress, channel = await self._resolve_context(interaction)
        if not progress or channel is None:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "This completion action is no longer available.",
                    ephemeral=True,
                )
            return

        overwrite = channel.overwrites_for(interaction.user)
        if overwrite.send_messages is True:
            await interaction.response.send_message(
                "Questions are already enabled in this channel.",
                ephemeral=True,
            )
            return

        overwrite.read_messages = True
        overwrite.read_message_history = True
        overwrite.send_messages = True

        try:
            await channel.set_permissions(
                interaction.user,
                overwrite=overwrite,
                reason="Graduate kept channel open for questions or feedback",
            )

            await interaction.response.edit_message(
                view=GraduationActionsView(
                    self.db,
                    interaction.user,
                    questions_enabled=True,
                ),
            )
            await interaction.followup.send(
                "Questions and feedback are now enabled. Send your message here when ready.",
                ephemeral=True,
            )
        except discord.Forbidden:
            logger.warning(
                f"Missing permission to reopen completed channel {channel.id} for messaging"
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "I could not open this channel for messages. Ask an admin to check my permissions.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "I could not open this channel for messages. Ask an admin to check my permissions.",
                    ephemeral=True,
                )
        except Exception as exc:
            logger.error(f"GraduationActionsView.keep_open: {exc}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Something went wrong while opening this channel for questions.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "Something went wrong while opening this channel for questions.",
                    ephemeral=True,
                )
