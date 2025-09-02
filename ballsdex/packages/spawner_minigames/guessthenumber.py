from typing import TYPE_CHECKING
import asyncio
import random
import discord
from discord.ui import View, Button
from ballsdex.core.utils.logging import log_action
from ballsdex.packages.countryballs.countryball import BallSpawnView

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class GTNView(View):
    def __init__(self, bot: "BallsDexBot"):
        super().__init__(timeout=90)
        self.bot = bot
        self.counts = {str(i): 0 for i in range(1, 10)}  # votes per number
        self.clicked_users: list[int] = []
        self.message: discord.Message | None = None
        self.numbers = list(range(1, 10))

        # dynamically add number buttons
        for n in self.numbers:
            button = Button(
                label=str(n),
                style=discord.ButtonStyle.secondary,
                custom_id=str(n)
            )
            button.callback = self.callback
            self.add_item(button)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id in self.clicked_users:
            return await interaction.response.send_message(
                "You already made your decision!",
                ephemeral=True,
            )

        buttonid = interaction.data["custom_id"]
        self.clicked_users.append(interaction.user.id)
        self.counts[buttonid] += 1
        await interaction.response.send_message(
            "Thanks for your decision!",
            ephemeral=True,
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)


async def guess_the_number(
    bot: "BallsDexBot",
    channel: discord.TextChannel,
    spawn_amount: int,
    number: int | None = None,
):
    view = GTNView(bot)
    picked_number = number or random.choice(view.numbers)

    # log which number was picked
    await log_action(picked_number, bot)

    # send the game prompt
    view.message = await channel.send(
        "Guess the number I picked and get a free Mass Spawn!\n"
        "-# You have a minute to guess. "
        "Click a button to make your guess, you can't revert back once chosen.",
        view=view,
    )

    # wait for guesses
    await asyncio.sleep(60)

    if any(view.counts.values()):  # at least one vote
        highest = max(view.counts, key=view.counts.get)
        if picked_number == int(highest):
            await channel.send(
                f"You picked {highest}\n"
                f"You guessed it right! My number was {picked_number}. "
                "Enjoy your reward!",
                reference=view.message,
            )
            for _ in range(spawn_amount):
                cb = await BallSpawnView.get_random(bot)
                await cb.spawn(channel)
        else:
            await channel.send(
                f"You picked {highest}\n"
                f"Sorry, you guessed wrong, my number was {picked_number}. "
                "Better luck next time!",
                reference=view.message,
            )
    else:
        await channel.send(
            "Nobody made a guess, I think no one wants a reward.",
            reference=view.message,
        )
