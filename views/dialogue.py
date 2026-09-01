from typing import Callable, List, Optional, Tuple

import discord

import config
from utils.logger import logger


class DialogueView(discord.ui.LayoutView):
    """
    Interactive Components V2 container that drives the step-by-step
    training dialogue.

    Each "Gamblors" line becomes a clickable button (the user's response).
    "Intern" lines are displayed in the container body automatically.

    Rendered as a single card (title, body, progress, button) to match the
    look of VideoDayView, instead of separate title/content embeds.

    The view is posted in the user's private training thread.
    Only the enrolled user can interact with it.
    """

    def __init__(
        self,
        title: str,
        content: List[Tuple[str, str]],
        on_complete: Optional[Callable] = None,
        user_id: Optional[int] = None,
        timeout: float = 600,
        on_button_click: Optional[Callable] = None,
        banner_filename: Optional[str] = None,
    ):
        super().__init__(timeout=timeout)
        self.title = title
        self.content = content
        self.on_complete_callback = on_complete
        self.on_button_click = on_button_click
        self.user_id = user_id
        self.banner_filename = banner_filename
        self.current_index: int = 0
        self.message: Optional[discord.Message] = None
        self._completed = False

        self._header = discord.ui.TextDisplay(f"## {title}")
        self._body = discord.ui.TextDisplay(self._body_text())
        self._button = discord.ui.Button()

        container_children = []
        if banner_filename:
            container_children.append(
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem(f"attachment://{banner_filename}")
                )
            )
        container_children += [
            self._header,
            self._body,
            discord.ui.ActionRow(self._button),
        ]

        self.add_item(
            discord.ui.Container(
                *container_children,
                accent_colour=config.EMBED_COLOR,
            )
        )

        self._configure_button()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Reject button presses from users other than the enrolled trainee."""
        if self.user_id and interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your training channel.", ephemeral=True
            )
            return False
        return True

    def _body_text(self) -> str:
        speaker, message = self.content[self.current_index]
        progress = f"-# {speaker}  •  {self.current_index + 1}/{len(self.content)}"
        return f"{message}\n\n{progress}"

    def _configure_button(self):
        """Point the single button at the current step's action."""
        at_end = self.current_index >= len(self.content) - 1

        if at_end:
            self._button.label = "Complete"
            self._button.style = discord.ButtonStyle.success
            self._button.custom_id = "dialogue_complete"
            self._button.callback = self._on_complete
        else:
            next_speaker, next_msg = self.content[self.current_index + 1]
            if next_speaker == "Gamblors":
                label = next_msg[:77] + "..." if len(next_msg) > 80 else next_msg
            else:
                label = "Next"

            self._button.label = label
            self._button.style = discord.ButtonStyle.primary
            self._button.custom_id = "dialogue_next"
            self._button.callback = self._on_next

    async def _on_next(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if self.on_button_click:
            try:
                self.on_button_click()
            except Exception as exc:
                logger.warning(f"on_button_click hook error: {exc}")

        self.current_index += 1
        self._body.content = self._body_text()
        self._configure_button()
        try:
            await interaction.message.edit(view=self)
        except Exception as exc:
            logger.error(f"DialogueView._on_next edit failed: {exc}")

    async def _on_complete(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if self.on_button_click:
            try:
                self.on_button_click()
            except Exception as exc:
                logger.warning(f"on_button_click hook error: {exc}")

        self._completed = True
        self._button.disabled = True

        try:
            await interaction.message.edit(view=self)
        except Exception as exc:
            logger.error(f"DialogueView._on_complete edit failed: {exc}")

        if self.on_complete_callback:
            try:
                await self.on_complete_callback(interaction.user)
            except Exception as exc:
                logger.error(f"on_complete_callback raised: {exc}")

        logger.info(f"User {interaction.user.id} completed a dialogue")

    def _spawn_resumed_view(self) -> "DialogueView":
        timeout = self.timeout if self.timeout is not None else 600
        resumed_view = DialogueView(
            self.title,
            self.content,
            on_complete=self.on_complete_callback,
            user_id=self.user_id,
            timeout=timeout,
            on_button_click=self.on_button_click,
            banner_filename=self.banner_filename,
        )
        resumed_view.current_index = self.current_index
        resumed_view.message = self.message
        resumed_view._body.content = resumed_view._body_text()
        resumed_view._configure_button()
        return resumed_view

    async def on_timeout(self):
        if self._completed or not self.message:
            return

        try:
            resumed_view = self._spawn_resumed_view()
            resumed_view._body.content = (
                "-# Session timed out. Continue when ready.\n\n"
                + resumed_view._body.content
            )
            await self.message.edit(view=resumed_view)
        except Exception:
            pass
