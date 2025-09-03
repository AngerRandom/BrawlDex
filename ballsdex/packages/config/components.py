from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, View, button

from ballsdex.core.models import GuildConfig
from ballsdex.core.utils.logging import log_action
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class AcceptTOSView(View):
    """
    Button prompting the admin setting up the bot to accept the terms of service.
    """

    def __init__(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        channel: discord.TextChannel,
        new_player: discord.Member,
        silent: bool,
        chinese_skin_toggle: bool,
        fanmade_skin_toggle: bool,
        fanmade_brawler_toggle: bool,
    ):
        super().__init__()
        self.original_interaction = interaction
        self.channel = channel
        self.new_player = new_player
        self.message: Optional[discord.Message] = None
        self.silent = silent
        self.chinese_skin_toggle = chinese_skin_toggle
        self.fanmade_skin_toggle = fanmade_skin_toggle
        self.fanmade_brawler_toggle = fanmade_brawler_toggle

        self.add_item(
            Button(
                style=discord.ButtonStyle.link,
                label="Terms of Service",
                url=settings.terms_of_service,
            )
        )
        self.add_item(
            Button(
                style=discord.ButtonStyle.link,
                label="Privacy policy",
                url=settings.privacy_policy,
            )
        )

    async def interaction_check(self, interaction: discord.Interaction["BallsDexBot"]) -> bool:
        if interaction.user.id != self.new_player.id:
            await interaction.response.send_message(
                "You are not allowed to interact with this menu.", ephemeral=True
            )
            return False
        return True

    @button(
        label="Accept",
        style=discord.ButtonStyle.success,
        emoji="\N{HEAVY CHECK MARK}\N{VARIATION SELECTOR-16}",
    )
    async def accept_button(
        self, interaction: discord.Interaction["BallsDexBot"], button: discord.ui.Button
    ):
        config, created = await GuildConfig.get_or_create(guild_id=interaction.guild_id)
        config.spawn_channel = self.channel.id  # type: ignore
        config.enabled = True
        config.silent = self.silent
        config.chinese_skin_toggle = self.chinese_skin_toggle
        config.fanmade_skin_toggle = self.fanmade_skin_toggle
        config.fanmade_brawler_toggle = self.fanmade_brawler_toggle
        await config.save()
        interaction.client.dispatch(
            "ballsdex_settings_change", interaction.guild, channel=self.channel, enabled=True
        )
        self.stop()
        if self.message:
            button.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
        await interaction.response.send_message(
            f"The new spawn channel was successfully set to {self.channel.mention}.\n"
            f"{settings.collectible_name.title()}s will start spawning as"
            " users talk unless the bot is disabled."
        )
        await log_action(
            f"{interaction.guild.name} activated BrawlDex's spawn system.",
            interaction.client
        )

    async def on_timeout(self) -> None:
        if self.message:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
