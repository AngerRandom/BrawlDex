from typing import TYPE_CHECKING
import asyncio
import random
import discord
from discord.ui import button, View, Button
from ballsdex.core.utils.logging import log_action
from ballsdex.packages.countryballs.countryball import BallSpawnView

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

class GTNView(View):
    def __init__(self, bot: "BallsDexBot"):
        super().__init__(timeout=90)
        self.counts = {
          "1": 0,
          "2": 0,
          "3": 0,
          "4": 0,
          "5": 0,
          "6": 0,
          "7": 0,
          "8": 0,
          "9": 0
        }
        self.clicked_users = []
        self.message = discord.Message
        self.numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9]

    for n in self.numbers:
        button = Button(
            label=str(n),
            style=discord.ButtonStyle.secondary,
            custom_id=str(n)
        )
        button.callback = self.callback
        self.add_item(button)
        
    async def callback(self, interaction: discord.Interaction["BallsDexBot"]):
      if interaction.user.id in self.clicked_users:
        return await interaction.response.send_message("You are already made your decision!", ephemeral=True)
      else:
        buttonid = interaction.data['custom_id']
        self.clicked_users.append(interaction.user.id)
        self.counts[buttonid] += 1
        await interaction.response.send_message("Thanks for your decision!", ephemeral=True)
    
    async def on_timeout(self):
      for item in self.children:
            item.disabled = True

      await self.message.edit(view=self)
      
async def guess_the_number(
    self, 
    bot: "BallsDexBot",
    channel: discord.TextChannel, 
    spawn_amount: int,
    number: int | None = None
):
  view = GTNView()
  picked_number = number
  if not picked_number:
      picked_number = random.choice(view.numbers)
  await log_action(picked_number, bot)
  view.message = await channel.send("Guess the number I picked and get a free Mass Spawn!\n-# You have a minute to guess. Click a button to make your guess, you can't revert back your decision once you picked a number.", view=view)
  await asyncio.sleep(60)
  if view.counts:
    highest = max(view.counts, key=view.counts.get)
    if picked_number == int(highest):
      await channel.send(f"You picked {highest}\nYou guessed it right! My guess was {picked_number}. Enjoy your reward!", reference=view.message)
      for i in range(spawn_amount):
          cb = await BallSpawnView.get_random(bot)
          await cb.spawn(channel)
    else:
      await channel.send(f"You picked {highest}\nSorry, you guessed it wrong, my guess was {picked_number}. Better luck next time!", reference=view.message)
      
  else:
    await channel.send("Nobody made a guess, I think no one wants a reward.", reference=view.message)
    return
