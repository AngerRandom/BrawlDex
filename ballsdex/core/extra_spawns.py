from typing import TYPE_CHECKING
import asyncio
import logging
import random
import discord
from discord.ext import commands
from discord import app_commands
from ballsdex.settings import settings
from ballsdex.core.models import Ball, Special
from ballsdex.packages.countryballs.countryball import BallSpawnView
from ballsdex.core.bot import BallsDexBot


log = logging.getLogger("ballsdex.core.extra_spawns")

@app_commands.guilds(*settings.admin_guild_ids)
@app_commands.default_permissions(administrator=True)
class Spawner(commands.Cog):
  def __init__(self, bot: BallsDexBot):
    self.bot = bot
    self.p2wtask = None
    self.basictask = None
    
    async def pay_to_win_spawner(self):
        channel = self.bot.get_channel(1391136498769723432)
        while True:
            spawn_time = 0
            spawn_amount = 0
            boost_count = channel.guild.premium_subscription_count
            if boost_count <= 15:
                spawn_time = 15*60
                spawn_amount = 1
            elif boost_count == 16:
                spawn_time = 14*60
                spawn_amount = 1
            elif boost_count == 17:
                spawn_time = 13*60
                spawn_amount = 2
            elif boost_count == 18:
                spawn_time = 12*60
                spawn_amount = 2
            elif boost_count == 19:
                spawn_time = 11*60
                spawn_amount = 2
            elif boost_count >= 20:
                spawn_time = 10*60
                spawn_amount = 3
            else:
                pass
            special_obj = ""
            options = [None, "Brawl Pass", "Brawl Pass Plus"]
            weights = [40, 40, 20]
            picked_special = random.choices(options, weights=weights, k=1)[0]
            if not picked_special:
                pass
            else:
                special_obj = await Special.get(name=str(picked_special))
            try:
                for i in range(spawn_amount):
                    ball = await BallSpawnView.get_random(self.bot)
                    ball.special = special_obj
                    await ball.spawn(channel)

            except Exception as e:
                log.error(f"An error occurred (P2W)", exc_info=e)

            await asyncio.sleep(spawn_time)

    async def basic_spawner(self):
        channel = self.bot.get_channel(1295410565765922862)
        while True:
            spawn_time = 0
            spawn_amount = 0
            boost_count = channel.guild.premium_subscription_count
            if boost_count <= 15:
                spawn_time = 15*60
                spawn_amount = 1
            elif boost_count == 16:
                spawn_time = 14*60
                spawn_amount = 1
            elif boost_count == 17:
                spawn_time = 13*60
                spawn_amount = 2
            elif boost_count == 18:
                spawn_time = 12*60
                spawn_amount = 2
            elif boost_count == 19:
                spawn_time = 11*60
                spawn_amount = 2
            elif boost_count >= 20:
                spawn_time = 10*60
                spawn_amount = 3
            else:
                pass
            try:
                for i in range(spawn_amount):
                    ball = await BallSpawnView.get_random(self.bot)
                    await ball.spawn(channel)

            except Exception as e:
                log.error(f"An error occurred (Basic)", exc_info=e)

            await asyncio.sleep(spawn_time)

    @commands.Cog.listener()
    async def on_ready(self):
        while not self.bot.operational:
            await asyncio.sleep(0.1)
        else:
            log.info("Attempting to enable the extra spawns...")
            try:
                self.p2wtask = asyncio.create_task(self.pay_to_win_spawner())
                log.info("P2W spawner is successfully enabled!")
                self.basictask = asyncio.create_task(self.basic_spawner(self))
                log.info("Basic spawner is successfully enabled!")
            except Exception as e:
                log.critical("Failed to enable one of the extra spawns.", exc_info=e)

    @app_commands.command(name="refresh_spawns", description="Restart and refresh the spawners!")
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def refresh_spawners(self, interaction: discord.Interaction[BallsDexBot]):
        try:
            self.p2wtask.cancel()
            self.p2wtask = None
            log.info("P2W spawner stopped by the command. Attempting to restart...")
            self.p2wtask = asyncio.create_task(self.pay_to_win_spawner())
            log.info("P2W spawner successfully restarted!")
            self.basictask.cancel()
            self.basictask = None
            log.info("Basic spawner stopped by the command. Attempting to restart...")
            self.basictask = asyncio.create_task(self.basic_spawner())
            log.info("Basic spawner successfully restarted!")
            await interaction.response.send_message("Done!", ephemeral=True)
        except Exception as e:
            log.critical("Failed to restart the spawns.", exc_info=e)
            await intetaction.response.send_message("An error occurred. Please check the logs for more information.", ephemeral=True)
            return

async def setup(bot: BallsDexBot):
    await bot.add_cog(Spawner(bot))
