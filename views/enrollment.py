import discord
import config
from typing import Callable

from utils.logger import logger

_BANNER_URL = "https://cdn.discordapp.com/attachments/1474746304608473200/1501241764525375649/bot_banner.png?ex=69fb5bd8&is=69fa0a58&hm=91e56d6121d9557b6b42cc219ddf6102850d0e8c3dd23f62aaa8b505b23610d0&"

_DESCRIPTION = (
    "Welcome to the **8-Day Luckmaxxing Training Program**.\n\n"
    "Transform from an average gamblor into a statistical anomaly. "
    "Daily interactive lessons will be delivered in your own private channel.\n\n"
    "**What to expect**\n"
    "• Intro + Day 1 on enrollment\n"
    "• Days 2 – 8 delivered automatically every 24 hours\n"
    "• Click through dialogue to progress\n"
    "• Scientifically-backed luck cultivation techniques\n\n"
    "**Requirements**\n"
    "• A valid enrollment code from an admin\n"
    "• Commitment to daily practice\n\n"
    "Click **Enroll** and enter your code to begin."
)


class EnrollmentModal(discord.ui.Modal, title="Enter Enrollment ID"):
    """
    Modal that pops up when a user clicks the Enroll button.
    Accepts a 5-character enrollment code and passes it to the provided callback.
    """

    enrollment_id = discord.ui.TextInput(
        label="Enrollment ID",
        placeholder="Enter your 5-character code (e.g. XKP87)",
        min_length=5,
        max_length=5,
        required=True,
    )

    def __init__(self, on_submit: Callable):
        super().__init__()
        self._on_submit = on_submit

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self._on_submit(interaction, self.enrollment_id.value.upper())
        except Exception as exc:
            logger.error(f"EnrollmentModal.on_submit: {exc}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred. Please try again.", ephemeral=True
                )


class EnrollmentView(discord.ui.LayoutView):
    """
    Persistent Components V2 container (survives bot restarts) that shows the
    enrollment card and Enroll button in the #luckmaxxing-protocol channel.
    """

    def __init__(self, on_enroll: Callable):
        """
        Args:
            on_enroll: async callback(interaction, enrollment_id_str)
        """
        super().__init__(timeout=None)  # Persistent – no expiry
        self._on_enroll = on_enroll

        button = discord.ui.Button(
            label="Enroll in Luckmaxxing Protocol",
            style=discord.ButtonStyle.success,
            custom_id="luckmaxx_enroll",  # Stable ID required for persistence
        )
        button.callback = self.enroll_button

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay("## Luckmaxxing Protocol"),
                discord.ui.MediaGallery(discord.MediaGalleryItem(media=_BANNER_URL)),
                discord.ui.TextDisplay(_DESCRIPTION),
                discord.ui.Separator(),
                discord.ui.TextDisplay("-# Gorillions await you."),
                discord.ui.ActionRow(button),
                accent_colour=config.EMBED_COLOR,
            )
        )

    async def enroll_button(self, interaction: discord.Interaction):
        try:
            modal = EnrollmentModal(on_submit=self._on_enroll)
            await interaction.response.send_modal(modal)
        except Exception as exc:
            logger.error(f"EnrollmentView.enroll_button: {exc}")
            await interaction.response.send_message(
                "An error occurred. Please try again.", ephemeral=True
            )
