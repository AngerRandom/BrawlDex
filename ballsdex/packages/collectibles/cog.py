from typing import TYPE_CHECKING, cast
import logging

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.settings import settings

from .brawlers import Brawlers as BrawlersGroup
from .skins import Skins as SkinsGroup
from .exclusives import Exclusives as ExclusivesGroup
from .gadgets import Gadgets as GadgetsGroup
from .starpowers import StarPowers as StarPowersGroup
from .gears import Gears as GearsGroup
from .hypercharges import Hypercharges as HyperchargesGroup

if TYPE_CHECKING:
  from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.collectibles")

class DonationRequest(View):
    def __init__(
        self,
        bot: "BallsDexBot",
        interaction: discord.Interaction["BallsDexBot"],
        countryball: BallInstance,
        new_player: Player,
    ):
        super().__init__(timeout=120)
        self.bot = bot
        self.original_interaction = interaction
        self.countryball = countryball
        self.new_player = new_player

    async def interaction_check(self, interaction: discord.Interaction["BallsDexBot"], /) -> bool:
        if interaction.user.id != self.new_player.discord_id:
            await interaction.response.send_message(
                "You are not allowed to interact with this menu.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True  # type: ignore
        try:
            await self.original_interaction.followup.edit_message(
                "@original", view=self  # type: ignore
            )
        except discord.NotFound:
            pass
        await self.countryball.unlock()

    @button(
        style=discord.ButtonStyle.success, emoji="\N{HEAVY CHECK MARK}\N{VARIATION SELECTOR-16}"
    )
    async def accept(self, interaction: discord.Interaction["BallsDexBot"], button: Button):
        self.stop()
        for item in self.children:
            item.disabled = True  # type: ignore
        self.countryball.favorite = False
        self.countryball.trade_player = self.countryball.player
        self.countryball.player = self.new_player
        await self.countryball.save()
        trade = await Trade.create(player1=self.countryball.trade_player, player2=self.new_player)
        await TradeObject.create(
            trade=trade, ballinstance=self.countryball, player=self.countryball.trade_player
        )
        await interaction.response.edit_message(
            content=interaction.message.content  # type: ignore
            + "\n\N{WHITE HEAVY CHECK MARK} The donation was accepted!",
            view=self,
        )
        await self.countryball.unlock()

    @button(
        style=discord.ButtonStyle.danger,
        emoji="\N{HEAVY MULTIPLICATION X}\N{VARIATION SELECTOR-16}",
    )
    async def deny(self, interaction: discord.Interaction["BallsDexBot"], button: Button):
        self.stop()
        for item in self.children:
            item.disabled = True  # type: ignore
        await interaction.response.edit_message(
            content=interaction.message.content  # type: ignore
            + "\n\N{CROSS MARK} The donation was denied.",
            view=self,
        )
        await self.countryball.unlock()


class DuplicateType(enum.StrEnum):
    countryballs = settings.plural_collectible_name
    specials = "specials"

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(dms=True, private_channels=True, guilds=True)
class BetterBrawlCog(commands.GroupCog, group_name=settings.players_group_cog_name):
    """
    Better version of the BrawlDex Collectible Manager cog!
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        
        assert self.__cog_app_commands_group__
        self.__cog_app_commands_group__.add_command(BrawlersGroup())
        self.__cog_app_commands_group__.add_command(SkinsGroup())
        self.__cog_app_commands_group__.add_command(ExclusivesGroup())
        self.__cog_app_commands_group__.add_command(GadgetsGroup())
        self.__cog_app_commands_group__.add_command(StarPowersGroup())
        self.__cog_app_commands_group__.add_command(GearsGroup())
        self.__cog_app_commands_group__.add_command(HyperchargesGroup())
