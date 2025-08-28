from typing import TYPE_CHECKING
import asyncio
import logging
import random
from ballsdex.core.models import Ball, Special
from ballsdex.packages.countryballs.countryball import BallSpawnView

if TYPE_CHECKING:
  from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.countryballs.extra_spawns")

async def pay_to_win_spawner(self):
    channel_id = 1391136498769723432
    while True:
        special_obj = ""
        options = [None, "Brawl Pass", "Brawl Pass Plus"]
        weights = [40, 40, 20]
        picked_special = random.choices(options, weights=weights, k=1)[0]
        if picked_special == None:
            pass
        else:
            special_obj = await Special.get(name=str(picked_special))
        try:
             ball = await BallSpawnView.get_random(self.bot)
             ball.special = special_obj
             await ball.spawn(bot.get_channel(channel_id))

        except Exception as e:
            log.error(f"An error occurred (P2W): {e}")

        await asyncio.sleep(180)

async def basic_spawner(self):
    channel_id = 1295410565765922862
    while True:
        try:
             ball = await BallSpawnView.get_random(self.bot)
             await ball.spawn(bot.get_channel(channel_id))

        except Exception as e:
            log.error(f"An error occurred (Basic): {e}")

        await asyncio.sleep(300)
