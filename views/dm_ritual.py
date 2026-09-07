import discord
import config
from typing import Callable

from utils.logger import logger

_BUTTON_ID = "luckmaxx_dm_ritual"


def _build_description(user: discord.abc.User | None) -> str:
    greeting = f"There he is. {user.mention}" if user else "There he is."
    return (
        f"{greeting}\n"
        "My realest drops, personalized bonuses and 3AM gamba signals travel on a private "
        "line.\n"
        "I'm a god.\n"
        "Gods don't do DMs.\n"
        "My intern does."
    )

_DM_MESSAGE = (
    "**GORILLION LINE ACTIVATED**\n\n"
    "i'm the intern's intern.\n"
    "Papi is currently collecting a debt from probability itself.\n"
    "all the goodies will drop here.\n"
    "do not close or mute this line or your bloodline remains middle class."
)


class DMRitualView(discord.ui.LayoutView):
    """
    Persistent Components V2 container posted right after onboarding.
    A single button does two things at once: DMs the user (so the bot can
    reliably reach them later, even away from this thread) and drops Day 1
    into the thread. Replaces the old separate DM-ritual + click-through
    Intro dialogue.
    """

    def __init__(self, on_confirm: Callable, user: discord.abc.User | None = None):
        """
        Args:
            on_confirm: async callback(interaction, dm_ok: bool) — called
                after the DM send attempt so the caller can persist the ack
                and drop Day 1. Fires regardless of whether the DM
                succeeded, since Day 1 delivery shouldn't depend on it.
            user: the enrollee to greet by mention. Omitted on the
                generic re-registration at cog_load (that instance is
                never actually sent — it only exists so Discord can route
                the button's persistent custom_id after a restart).
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
                discord.ui.TextDisplay(_build_description(user)),
                discord.ui.ActionRow(self._button),
                accent_colour=config.EMBED_COLOR,
            )
        )

    async def _on_click(self, interaction: discord.Interaction):
        dm_ok = True
        try:
            await interaction.user.send(_DM_MESSAGE)
        except discord.Forbidden:
            dm_ok = False
        except Exception as exc:
            logger.error(f"DMRitualView._on_click send failed: {exc}")
            dm_ok = False

        self._button.disabled = True
        self._button.label = "Reported to Papi"
        await interaction.response.edit_message(view=self)

        if not dm_ok:
            await interaction.followup.send(
                "I couldn't DM you — you likely have DMs from server members "
                "turned off. Enable them if you want drops there too.",
                ephemeral=True,
            )

        try:
            await self._on_confirm(interaction, dm_ok)
        except Exception as exc:
            logger.error(f"DMRitualView on_confirm callback raised: {exc}")
