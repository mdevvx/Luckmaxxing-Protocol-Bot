import discord
import config
from typing import Callable

from utils.logger import logger

_BUTTON_ID = "luckmaxx_dm_ritual"

_DESCRIPTION = (
    "One last thing before we begin: **report to Papi in private.**\n\n"
    "Click below and I'll send you a DM. From then on, that's where drops, "
    "offers, and anything time-sensitive will find you — even if you're away "
    "from this thread."
)


class DMRitualView(discord.ui.LayoutView):
    """
    Persistent Components V2 container posted right after onboarding.
    Getting the user to click it opens a DM channel with the bot so it can
    reliably reach them later. Non-blocking — training proceeds regardless.
    """

    def __init__(self, on_confirm: Callable):
        """
        Args:
            on_confirm: async callback(interaction) — called after a
                successful DM send so the caller can persist the ack.
        """
        super().__init__(timeout=None)
        self._on_confirm = on_confirm

        self._button = discord.ui.Button(
            label="Report to Papi",
            style=discord.ButtonStyle.primary,
            custom_id=_BUTTON_ID,
        )
        self._button.callback = self._on_click

        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(_DESCRIPTION),
                discord.ui.ActionRow(self._button),
                accent_colour=config.EMBED_COLOR,
            )
        )

    async def _on_click(self, interaction: discord.Interaction):
        try:
            await interaction.user.send(
                "Papi's got eyes on you now, Chief. This is where I'll reach you "
                "with drops, offers, and updates — keep your DMs open."
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I couldn't DM you — you likely have DMs from server members "
                "turned off. Enable them and click the button again.",
                ephemeral=True,
            )
            return
        except Exception as exc:
            logger.error(f"DMRitualView._on_click send failed: {exc}")
            await interaction.response.send_message(
                "Something went wrong sending the DM. Try again.", ephemeral=True
            )
            return

        try:
            await self._on_confirm(interaction)
        except Exception as exc:
            logger.error(f"DMRitualView on_confirm callback raised: {exc}")

        self._button.disabled = True
        self._button.label = "Reported to Papi"

        await interaction.response.edit_message(view=self)
