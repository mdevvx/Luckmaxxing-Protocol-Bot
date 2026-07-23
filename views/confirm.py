import discord


class ConfirmView(discord.ui.View):
    """Generic Yes/No confirmation. Only the invoking user may respond."""

    def __init__(self, user_id: int, *, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.value: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the person who ran this command can respond.", ephemeral=True
            )
            return False
        return True

    def _disable(self) -> None:
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Yes, unenroll", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = True
        self._disable()
        await interaction.response.edit_message(content="Unenrolling...", view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = False
        self._disable()
        await interaction.response.edit_message(content="Cancelled.", view=self)
        self.stop()
