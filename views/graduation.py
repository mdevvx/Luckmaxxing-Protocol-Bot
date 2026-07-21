from typing import Optional, Union

import discord

import config


class GraduationActionsView(discord.ui.LayoutView):
    """Static Components V2 container announcing training completion.

    The thread stays open permanently as the user's ongoing comms line, so
    this is an acknowledgement only — no close/delete action is offered.
    """

    def __init__(
        self,
        user: Optional[Union[discord.Member, discord.User]] = None,
    ):
        super().__init__(timeout=None)

        mention = user.mention if user else "Gamblor"
        children = [
            discord.ui.TextDisplay("## Luckmaxxing Protocol Complete"),
            discord.ui.TextDisplay(
                f"{mention}, you finished the 8-Day Luckmaxxing Protocol.\n\n"
                f"You are now a **{config.GRADUATE_ROLE_NAME}** and a **statistical anomaly**.\n\n"
                "This thread stays open — it's your line for updates, drops, and offers going forward."
            ),
            discord.ui.TextDisplay("-# Badge unlocked."),
        ]

        self.add_item(discord.ui.Container(*children, accent_colour=config.EMBED_COLOR))
