"""
pagination.py
=============
A small reusable paginated-embed view (Tier 3.4).

Give it a list of pre-built embeds; it shows one at a time with ◀ / ▶ buttons
(and a page counter). Used by the leaderboard, the resource list, and /questions.
Only the user who ran the command can flip pages.
"""

from __future__ import annotations

import discord

from config import Config


class Paginator(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed], author_id: int, *, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.embeds = embeds or []
        self.author_id = author_id
        self.index = 0
        self.message: discord.Message | None = None
        self._sync_state()

    def _sync_state(self) -> None:
        # Disable nav when there's nowhere to go; update the counter label.
        last = len(self.embeds) - 1
        self.prev_button.disabled = self.index <= 0
        self.next_button.disabled = self.index >= last
        self.counter.label = f"{self.index + 1}/{len(self.embeds)}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the person who ran the command can flip pages.", ephemeral=True
            )
            return False
        return True

    async def _show(self, interaction: discord.Interaction) -> None:
        self._sync_state()
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = max(0, self.index - 1)
        await self._show(interaction)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.primary, disabled=True)
    async def counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Non-interactive label button (shows current page).
        await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = min(len(self.embeds) - 1, self.index + 1)
        await self._show(interaction)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


def paginate(items: list, per_page: int | None = None) -> list[list]:
    """Split a flat list into page-sized chunks."""
    size = per_page or Config.PAGE_SIZE
    return [items[i : i + size] for i in range(0, len(items), size)] or [[]]
