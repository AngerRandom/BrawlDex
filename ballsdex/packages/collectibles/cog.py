from typing import TYPE_CHECKING, cast

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
