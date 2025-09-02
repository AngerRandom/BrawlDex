from typing import TYPE_CHECKING

from ballsdex.packages.spawner_minigames.cog import MassSpawnMinigames

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(MassSpawnMinigames(bot))
