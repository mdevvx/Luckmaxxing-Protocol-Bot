from typing import Optional

import discord

import config


class VideoDayView(discord.ui.LayoutView):
    """
    Components V2 container that presents a day's lesson as a link out to
    the tracked /watch page (the video itself is hosted on the website, not
    embedded in Discord, so watch completion can be tracked server-side).

    Layout: banner image (if one's been set for this day) -> title ->
    caption -> "Watch Video" link button, all inside a single Container so
    it renders as one card.

    Posted in the user's private training thread. Day progression is not
    driven by this view — it advances once the watch is recorded on the
    website's side.
    """

    def __init__(
        self,
        title: str,
        watch_url: str,
        caption: Optional[str] = None,
        banner_filename: Optional[str] = None,
    ):
        super().__init__(timeout=None)

        children = []
        if banner_filename:
            children.append(
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem(f"attachment://{banner_filename}")
                )
            )
        children.append(discord.ui.TextDisplay(f"## {title}"))
        if caption:
            children.append(discord.ui.TextDisplay(caption))
        children.append(discord.ui.Separator())
        children.append(
            discord.ui.ActionRow(
                discord.ui.Button(
                    label="Watch Video",
                    style=discord.ButtonStyle.link,
                    url=watch_url,
                )
            )
        )

        self.add_item(discord.ui.Container(*children, accent_colour=config.EMBED_COLOR))
