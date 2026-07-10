from typing import Callable, Optional

import discord

import config
from utils.logger import logger


class VideoDayView(discord.ui.LayoutView):
    """
    Components V2 container that presents a day's lesson as a video
    instead of the stepped text dialogue.

    Layout: title -> video (MediaGallery) -> Complete button, all inside
    a single Container so it renders as one card.

    The view is posted in the user's private training channel.
    Only the enrolled user can interact with it.
    """

    def __init__(
        self,
        title: str,
        video_url: str,
        caption: Optional[str] = None,
        on_complete: Optional[Callable] = None,
        user_id: Optional[int] = None,
        timeout: float = 600,
    ):
        super().__init__(timeout=timeout)
        self.on_complete_callback = on_complete
        self.user_id = user_id
        self.message: Optional[discord.Message] = None
        self._completed = False

        self._complete_button = discord.ui.Button(
            label="Complete",
            style=discord.ButtonStyle.success,
            custom_id="video_day_complete",
        )
        self._complete_button.callback = self._on_complete

        children = [
            discord.ui.TextDisplay(f"## {title}"),
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=video_url)),
        ]
        if caption:
            children.append(discord.ui.Separator())
            children.append(discord.ui.TextDisplay(caption))
        children.append(discord.ui.ActionRow(self._complete_button))

        self.add_item(discord.ui.Container(*children, accent_colour=config.EMBED_COLOR))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Reject button presses from users other than the enrolled trainee."""
        if self.user_id and interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your training channel.", ephemeral=True
            )
            return False
        return True

    async def _on_complete(self, interaction: discord.Interaction):
        await interaction.response.defer()

        self._completed = True
        self._complete_button.disabled = True

        try:
            await interaction.message.edit(view=self)
        except Exception as exc:
            logger.error(f"VideoDayView._on_complete edit failed: {exc}")

        if self.on_complete_callback:
            try:
                await self.on_complete_callback(interaction.user)
            except Exception as exc:
                logger.error(f"on_complete_callback raised: {exc}")

        logger.info(f"User {interaction.user.id} completed a video day")

    async def on_timeout(self):
        if self._completed or not self.message:
            return
        try:
            await self.message.edit(view=self)
        except Exception:
            pass


from typing import Callable, Optional

import discord

import config

from utils.logger import logger
