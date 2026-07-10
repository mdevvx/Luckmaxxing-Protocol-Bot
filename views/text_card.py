from typing import Optional, Union

import discord

import config


class TextCardView(discord.ui.LayoutView):
    """Non-interactive Components V2 container for a title + text-block card."""

    def __init__(
        self,
        title: str,
        *body: str,
        accent_colour: Optional[Union[discord.Colour, int]] = None,
    ):
        super().__init__(timeout=None)
        children = [discord.ui.TextDisplay(f"## {title}")]
        children.extend(discord.ui.TextDisplay(block) for block in body)
        self.add_item(
            discord.ui.Container(
                *children,
                accent_colour=(
                    accent_colour if accent_colour is not None else config.EMBED_COLOR
                ),
            )
        )
