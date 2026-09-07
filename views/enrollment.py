import os
from typing import Callable

import discord

import config
from utils.logger import logger

# Local asset instead of a hardcoded Discord CDN link — those URLs carry a
# signed expiry (ex=/is=/hm=) and go dead once it passes, since nothing here
# re-fetches a fresh one.
_BANNER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "assets", "enrollment_banner.jpg"
)
_BANNER_FILENAME = "enrollment_banner.jpg"


def enrollment_banner_file() -> discord.File | None:
    """Build a fresh attachment for the enrollment banner, or None if the
    asset is missing. discord.File wraps an open file handle, so a new one
    is needed per send — never reuse an instance across messages."""
    if not os.path.isfile(_BANNER_PATH):
        return None
    return discord.File(_BANNER_PATH, filename=_BANNER_FILENAME)

_DESCRIPTION = (
    "Gm, lil gamblor.\n\n"
    "For the next 8 days, Papi will tell you the story of a redacted peasant who looked "
    "variance dead in the eyes, rejected statistical poverty, and became a glitch in the "
    "Matrix.\n\n"
    "The kind of glitch the house has no edge over anymore.\n"
    "It just owes me now.\n"
    "Inshallah.\n\n"
    "Along the way, I'll hand you classified luckmaxxing knowledge: methods leaked from "
    "2033, the kind the CIA burned millions on and buried.\n"
    "Google it. I dare you.\n\n"
    "By Day 8, you either become statistically illegal or remain exit liquidity with a "
    "Discord account.\n"
    "Watch carefully. Complete the training. Reject all evidence to the contrary."
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
            label="Me wants to luckmaxx",
            style=discord.ButtonStyle.success,
            custom_id="luckmaxx_enroll",  # Stable ID required for persistence
        )
        button.callback = self.enroll_button

        children = [discord.ui.TextDisplay("## LUCKMAXXING PROTOCOL — INITIATION")]
        if os.path.isfile(_BANNER_PATH):
            children.append(
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem(f"attachment://{_BANNER_FILENAME}")
                )
            )
        children += [
            discord.ui.TextDisplay(_DESCRIPTION),
            discord.ui.Separator(),
            discord.ui.TextDisplay("-# Gorillions await you."),
            discord.ui.ActionRow(button),
        ]

        self.add_item(discord.ui.Container(*children, accent_colour=config.EMBED_COLOR))

    async def enroll_button(self, interaction: discord.Interaction):
        try:
            modal = EnrollmentModal(on_submit=self._on_enroll)
            await interaction.response.send_modal(modal)
        except Exception as exc:
            logger.error(f"EnrollmentView.enroll_button: {exc}")
            await interaction.response.send_message(
                "An error occurred. Please try again.", ephemeral=True
            )
