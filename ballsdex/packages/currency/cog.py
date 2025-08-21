import logging
import random
import sys
from typing import TYPE_CHECKING, Dict
from dataclasses import dataclass, field

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, button

import asyncio
import io

from ballsdex.core.models import (
    Ball,
    BallInstance,
    Regime,
    Player as PlayerModel,
)
from ballsdex.core.utils.transformers import (
    BallInstanceTransform,
    BallEnabledTransform,
)
from ballsdex.core.utils.utils import inventory_privacy, is_staff
from ballsdex.core.models import balls as countryballs
from ballsdex.settings import settings

from tortoise.exceptions import DoesNotExist

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot
log = logging.getLogger("ballsdex.packages.currency")

class UpgradeConfirmView(View):
    def __init__(self, author: discord.User | discord.Member, brawler: BallInstance, bot: "BallsDexBot", player: PlayerModel):
        super().__init__(timeout=60)
        self.bot = bot
        self.author = author
        self.brawler = brawler
        self.model = brawler.countryball
        self.player = player
        self.NextUpgradeCost = {2: 20, 3: 30, 4: 50, 5: 80, 6: 130, 7: 210, 8: 340, 9: 550, 10: 890, 11: 1440}

        SKIN_REGIMES = [22, 23, 24, 25, 26, 27, 37, 40, 39, 38, 35]
        self.ind_str = "Skin" if self.model.regime_id in SKIN_REGIMES else "Brawler"

        plevel_emojis = [
            1366783166941102081,
            1366783917314674698,
            1366784186941177977,
            1366784841487745034,
            1366784908575510558,
            1366785648370909327,
            1366785660605698058,
            1366786928338407424,
            1366786943790088345,
            1366788095227199569,
            1366788107747328122
        ]
        self.current_plvl = int((self.brawler.health_bonus + self.brawler.attack_bonus + 20) / 20 + 1)
        self.current_plvl_emoji = bot.get_emoji(plevel_emojis[self.current_plvl - 1])
        self.next_plvl_emoji = bot.get_emoji(plevel_emojis[self.current_plvl])

        self.hp_emoji = bot.get_emoji(1399770718794809385)
        self.atk_emoji = bot.get_emoji(1399770723060289557)
        self.pp_emoji = bot.get_emoji(1364807487106191471)
        self.brawler_emoji = bot.get_emoji(self.model.emoji_id)

        self.current_hp = int(self.model.health * float(f"1.{self.brawler.health_bonus}")) if float(f"1.{self.brawler.health_bonus}") != 1.100 else int(self.model.health * 2)
        self.current_atk = int(self.model.attack * float(f"1.{self.brawler.attack_bonus}")) if float(f"1.{self.brawler.attack_bonus}") != 1.100 else int(self.model.attack * 2)

        self.cost = self.NextUpgradeCost[self.current_plvl]
        future_health_bonus = self.brawler.health_bonus + 10
        future_attack_bonus = self.brawler.attack_bonus + 10
        self.new_hp = int(self.model.health * float(f"1.{future_health_bonus}")) if float(f"1.{future_health_bonus}") != 1.100 else int(self.model.health * 2)
        self.new_atk = int(self.model.attack * float(f"1.{future_attack_bonus}")) if float(f"1.{future_attack_bonus}") != 1.100 else int(self.model.attack * 2)

    @button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_upgrade(self, interaction: discord.Interaction["BallsDexBot"], button: Button):
        if interaction.user != self.author:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
        await interaction.edit_original_response(content="The operation was cancelled.")
        
    @button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm_upgrade(self, interaction: discord.Interaction["BallsDexBot"], button: Button):
        if interaction.user != self.author:
            await interaction.response.send_message("This is not your interaction!", ephemeral=True)
            return
     
        if player.powerpoints < self.cost:
            await interaction.edit_original_response(content=f"You're missing {self.cost-player.powerpoints}{self.pp_emoji} to upgrade [{self.model.country}](<https://brawldex.fandom.com/wiki/{self.model.country.replace(" ", "_")}>){self.brawler_emoji} to {self.next_plvl_emoji}.")
            return
        else:
            player.powerpoints -= self.cost
            await player.save(update_fields=("powerpoints",))
            self.brawler.health_bonus += 10; self.brawler.attack_bonus += 10
            await self.brawler.save()
            await interaction.edit_original_response(content=f"[{self.model.country}](<https://brawldex.fandom.com/wiki/{self.model.country.replace(" ", "_")}>){self.brawler_emoji} was upgraded from {self.current_plvl_emoji} to {self.next_plvl_emoji}!\n{self.current_hp}{self.hp_emoji}→{self.new_hp}{self.hp_emoji}  {self.current_atk}{self.atk_emoji}→{self.new_atk}{self.atk_emoji}")

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True
        try:
            await self.edit_original_response(view=self)
        except discord.NotFound:
            pass

        
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(dms=True, private_channels=True, guilds=True)
class Credits(commands.GroupCog, group_name="credits"):
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self.CostByRarity = {"rare": 160, "super_rare": 430, "epic": 925, "mythic": 1900, "legendary": 3800}
        self.ExcludeOptions = ["ultra_legendary",]
        self.ExcludedItems = ["trunk"]
    
    @app_commands.command(name="info")
    @app_commands.checks.cooldown(1, 20, key=lambda i: i.channel.id)
    async def credits_info(
        self,
        interaction: discord.Interaction,
        
    ):
        """
        Show Credits Shop Prices
        """
        
        mjc = self.bot.get_emoji(1364877727601004634)
        mjrare = self.bot.get_emoji(1330493249235714189)
        mjsuperrare = self.bot.get_emoji(1330493410884456528)
        mjepic = self.bot.get_emoji(1330493427011555460)
        mjmythic = self.bot.get_emoji(1330493448469483580)
        mjlegendary = self.bot.get_emoji(1330493465221529713)
        mjultra = self.bot.get_emoji(1368271368382320761)
        embed = discord.Embed(
            title="Credits Info",
            description=f"{mjc} **Prices** {mjc} \n\nRare{mjrare}: 160{mjc} \nSuper Rare{mjsuperrare}: 430{mjc} \nEpic{mjepic}: 925{mjc} \nMythic{mjmythic}: 1900{mjc} \nLegendary{mjlegendary}: 3800{mjc} \n\n-# {mjultra} Ultra Legendaries are unpurchaseable.",
            color=discord.Color.og_blurple()
)       
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="claim")
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.user.id)
    async def credits_claim(
        self,
        interaction: discord.Interaction,
        brawler: BallEnabledTransform,
        
    ):
        """
        Claim a Brawler using Credits!
        
        Parameters
        ----------
        brawler: Ball
            The Brawler you want.
        """
        Reg = await Regime.get(id=brawler.regime_id)
        if Reg.name.lower().strip().replace(" ", "_") in self.ExcludeOptions or brawler.country.lower() in self.ExcludedItems:
            await interaction.response.send_message(f"{brawler.country} can not be claimed.",ephemeral=True)
            return
        if Reg.name.lower().strip().replace(" ", "_") not in self.CostByRarity:
            await interaction.response.send_message(f"Non-brawlers can not currently be claimed.",ephemeral=True)
            return
        
        playerm, _ = await PlayerModel.get_or_create(discord_id=interaction.user.id)
        
        cost = self.CostByRarity[(await Regime.get(id=brawler.regime_id)).name.lower().strip().replace(" ", "_")]
        if cost is None:
            await interaction.response.send_message(f"{brawler.country} can not currently be claimed.",ephemeral=True)
            return
        if playerm.credits >= cost:
            await interaction.response.defer(thinking=True)
            playerm.credits -= cost
            await playerm.save(update_fields=("credits",))
            inst = await BallInstance.create(
                ball=brawler,
                player=playerm,
                attack_bonus=0,
                health_bonus=0,
                server_id=interaction.guild.id if not interaction.guild == None else None
            )
            data, file, view = await inst.prepare_for_message(interaction)
            try:
                await interaction.followup.send(interaction.user.mention+", your Brawler has been claimed.\n\n"+data, file=file, view=view)
            finally:
                file.close()
                log.debug(f"{interaction.user.id} claimed a {brawler.country}")       

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(dms=True, private_channels=True, guilds=True)
class PowerPoints(commands.GroupCog, group_name="powerpoints"):
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
    
    @app_commands.command(name="shop")
    @app_commands.checks.cooldown(1, 20, key=lambda i: i.channel.id)
    async def pp_chart(
        self,
        interaction: discord.Interaction,
        
    ):
        """
        Show Power Points Leveling Chart
        """
        
        mj = self.bot.get_emoji(1364807487106191471)
        embed = discord.Embed(
            title="Power Points Shop",
            description=f"Power Level 2: 20{mj} (Total: 20)\nPower Level 3: 30{mj} (Total: 50)\nPower Level 4: 50{mj} (Total: 100)\nPower Level 5: 80{mj} (Total: 180)\nPower Level 6: 130{mj} (Total: 310)\nPower Level 7: 210{mj} (Total: 520)\nPower Level 8: 340{mj} (Total: 860)\nPower Level 9: 550{mj} (Total: 1410)\nPower Level 10: 890{mj} (Total: 2300)\nPower Level 11: 1440{mj} (Total: 3740)\n\nNote: Each power level gives a +10% stat boost.",
            color=discord.Color.pink()
)       
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="upgrade")
    @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
    @app_commands.checks.has_any_role(*settings.root_role_ids)
    async def pp_upgrade(
        self,
        interaction: discord.Interaction,
        brawler: BallInstanceTransform,
        
    ):
        """
        Upgrade a Brawler to the next Power Level.
        
        Parameters
        ----------
        brawler: BallInstance
            The Brawler you want to Upgrade.
        """
        
        playerm = await PlayerModel.get(discord_id=interaction.user.id)
        if not brawler or brawler.player != playerm:
            return
        view = UpgradeConfirmView(author=interaction.user, brawler=brawler, bot=self.bot, player=playerm)
        if view.brawler.health_bonus == 100 and view.brawler.attack_bonus == 100:
            await interaction.response.send_message(f"This {view.ind_str} is already at maximum Power Level!", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Are you sure you want to upgrade this {view.ind_str}?\n"
            f"**[{view.model.country}](<https://brawldex.fandom.com/wiki/{view.model.country.replace(" ", "_")}>)**{view.brawler_emoji}{view.current_plvl_emoji}→{view.next_plvl_emoji} ({playerm.powerpoints}{view.pp_emoji}→{playerm.powerpoints-view.cost}{view.pp_emoji})\n"
            f"{view.current_hp}{view.hp_emoji}→{view.new_hp}{view.hp_emoji}  {view.current_atk}{view.atk_emoji}→{view.new_atk}{view.atk_emoji}",
            view=view,
            ephemeral=False
        )



@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(dms=True, private_channels=True, guilds=True)
class Currency(commands.Cog):
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self.CurrencyPortion = {"powerpoints": 30, "credits": 45}


    @app_commands.command(name="freebie")
    @app_commands.checks.cooldown(1, 86400, key=lambda i: i.user.id)
    async def daily_freebie(
        self,
        interaction: discord.Interaction,
        
    ):
        """
        Claim your daily freebie.
        """
        fortunes = [
                "¡Sin dolor no hay gloria!",
                "All work and no Brawl makes Gus a dull boy.",
                "An Edgar in the hand is worth two in the bush.",
                "Apples = oranges.",
                "Be the random you wish to see in the world.",
                "Caw caw! (ancient Crow proverb)",
                "Do or do not. There is no try.",
                "Eat. Sleep. Brawl. Repeat.",
                "Expect the unexpected.",
                "Fall seven times, stand up eight.",
                "Fortune favors the Brawl.",
                "Git gud.",
                "help, i am being held hostage in a fortune cookie factory",
                "If at first you don't succeed, Brawl, Brawl again.",
                "If your randoms are good... you are the bad random.",
                "It could be worse!",
                "Just one more Brawl.",
                "Kit will use his Super on you from the bushes.",
                "Live, laugh, Brawl.",
                "Remember to Hypercharge your day!",
                "Same time tomorrow?",
                "Sometimes it really is just a skill issue.",
                "Spike is ALWAYS watching.",
                "Stay hydrated.",
                "The Gems you seek are closer than they appear.",
                "The journey to Pro begins with the first Brawl.",
                "The next Starr Drop is Legendary. For sure.",
                "The real Trophies are the friends we made along the way.",
                "The trophy climb will be hard, but worth it.",
                "There is a learning in every defeat.",
                "Those in glass houses shouldn't activate Supers.",
                "Today's matches will be legendary, just like that Brawler you're about to unlock.",
                "Today is a good day to carry a random.",
                "Today is the day. Do that trickshot!",
                "Today is time to take on a new challenge... play Hank.",
                "Touch grass. But come back tomorrow.",
                "Victory is temporary. Brawl is forever.",
                "Who do you think you are? I am.",
                "You are Prawn ready!",
                "You are the good random your team deserves. But not the one they need right now.",
                "You can't choose your family but you can choose your Club!",
                "You will find your perfect 2v2 partner.",
                "You will not have bad randoms today.",
                "Your favorite Brawler will receive a buff... eventually.",
                "Your next teammates will be Mortis and Edgar.",
                "Your Ranked Season will go smoothly.",
                "[404 FORTUNE NOT FOUND]"
        ]
        fortune_cookie_1 = self.bot.get_emoji(1364828492922880151)
        fortune_cookie_2 = self.bot.get_emoji(1364828507581976586)
        funny_freebie_sticker = self.bot.get_sticker(1376630320144715809)
        sticker_array = []
        sticker_array.append(funny_freebie_sticker)
        sticker_server_id = settings.admin_guild_ids[0]

            
        options = ["powerpoints", "credits", "powerpoints10", "credits10"]
        chances = [96, 96, 4, 4]

        trigger_sticker = True
        choice = random.choices(options, weights=chances, k=1)[0]
        if choice != "powerpoints":
            trigger_sticker = False
        picked_fortune = random.choice(fortunes)
        
        player, _ = await PlayerModel.get_or_create(discord_id=interaction.user.id)  
        await interaction.response.defer(thinking=True)    
        cmnt = self.CurrencyPortion[choice.replace("10", "")] 
        jackpot = choice
        if "10" in choice:
            choice = choice.replace("10", "")
            jackpot = jackpot.replace("10", ", You hit the Jackpot, You get 10x the reward!")
            cmnt *= 10
        setattr(player, choice, getattr(player, choice) + cmnt)
        await player.save(update_fields=(choice,))
        cmd_msg = await interaction.followup.send(f"You received your {cmnt} {jackpot}\n{fortune_cookie_1}*{picked_fortune}*{fortune_cookie_2}", ephemeral=True)
        if interaction.guild and interaction.guild.id == sticker_server_id and trigger_sticker == True:
            await interaction.channel.send(stickers=sticker_array, reference=cmd_msg)
