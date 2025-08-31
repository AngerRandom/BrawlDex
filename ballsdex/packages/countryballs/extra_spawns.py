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
    channel = self.get_channel(1391136498769723432)
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
                ball = await BallSpawnView.get_random(self)
                ball.special = special_obj
                await ball.spawn(channel)

        except Exception as e:
            log.error(f"An error occurred (P2W): {e}")

        await asyncio.sleep(spawn_time)

async def basic_spawner(self):
    channel = self.get_channel(1295410565765922862)
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
                ball = await BallSpawnView.get_random(self)
                await ball.spawn(channel)

        except Exception as e:
            log.error(f"An error occurred (Basic): {e}")

        await asyncio.sleep(spawn_time)
