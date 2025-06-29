import logging
import random
import sys
from datetime import datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.app_commands.translator import (
    TranslationContext,
    TranslationContextLocation,
    locale_str,
)
from discord.ext import commands

from ballsdex import __version__ as ballsdex_version
from ballsdex.core.models import Ball, BallInstance, Player
from ballsdex.core.models import balls as countryballs
from ballsdex.core.utils.formatting import pagify
from ballsdex.core.utils.tortoise import row_count_estimate
from ballsdex.settings import settings

from .license import LicenseInfo

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.info")

sections = [
    {"title": "INTRO", "description": f"{settings.bot_name} Discord bot\n"},
    {"title": "TUTORIAL", "description": "This is the second section."},
    {"title": "COMMANDS", "description": "This is the third section."}
]

class SectionPaginator(discord.ui.View):
    def __init__(self, sections: list[dict], author: discord.User):
        super().__init__(timeout=300)
        self.sections = sections
        self.author = author
        self.message = None
        self.current_index = 0  # Track active section
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()  # Remove old buttons
        for idx in range(len(self.sections)):
            style = discord.ButtonStyle.success if idx == self.current_index else discord.ButtonStyle.secondary
            button = discord.ui.Button(label=str(idx + 1), style=style)
            button.callback = self.make_callback(idx)
            self.add_item(button)

    def make_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            # 🔒 Restrict to original user
            if interaction.user.id != self.author.id:
                await interaction.response.send_message(
                    "You can't use these buttons — this paginator belongs to someone else.",
                    ephemeral=True
                )
                return

            self.current_index = index
            self.update_buttons()  # Update styles
            embed = self.make_embed(index)
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    def make_embed(self, index: int) -> discord.Embed:
        section = self.sections[index]
        embed = discord.Embed(
            title=section["title"],
            description=section["description"],
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Section {index + 1} of {len(self.sections)}")
        return embed

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass


def mention_app_command(app_command: app_commands.Command | app_commands.Group) -> str:
    if "mention" in app_command.extras:
        return app_command.extras["mention"]
    else:
        if isinstance(app_command, app_commands.ContextMenu):
            return f"`{app_command.name}`"
        else:
            return f"`/{app_command.name}`"


class Info(commands.Cog):
    """
    Simple info commands.
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    async def _get_10_balls_emojis(self) -> list[discord.Emoji]:
        balls: list[Ball] = random.choices(
            [x for x in countryballs.values() if x.enabled], k=min(10, len(countryballs))
        )
        emotes: list[discord.Emoji] = []

        for ball in balls:
            if emoji := self.bot.get_emoji(ball.emoji_id):
                emotes.append(emoji)

        return emotes
        
    @app_commands.command()
    async def help(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        Need help with using the bot?
        """
        try:
            balls = await self._get_10_balls_emojis()
        except Exception:
            log.error("Failed to fetch 10 balls emotes", exc_info=True)
            balls = []

        balls_count = len([x for x in countryballs.values() if x.enabled])
        players_count = await row_count_estimate("player")
        balls_instances_count = await row_count_estimate("ballinstance")

        if self.bot.startup_time is not None:
            uptime_duration = datetime.now() - self.bot.startup_time
            formatted_uptime = str(uptime_duration).split(".")[0]
        else:
            formatted_uptime = "N/A"

        assert self.bot.user
        assert self.bot.application
        try:
            assert self.bot.application.install_params
        except AssertionError:
            invite_link = discord.utils.oauth_url(
                self.bot.application.id,
                permissions=discord.Permissions(
                    manage_webhooks=True,
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True,
                    attach_files=True,
                    use_external_emojis=True,
                    add_reactions=True,
                ),
                scopes=("bot", "applications.commands"),
            )
        else:
            invite_link = discord.utils.oauth_url(
                self.bot.application.id,
                permissions=self.bot.application.install_params.permissions,
                scopes=self.bot.application.install_params.scopes,
            )
        bot_info = await self.bot.application_info()
        if bot_info.team:
            owner = bot_info.team.name
        else:
            owner = bot_info.owner
        owner_credits = "by the team" if bot_info.team else "by"
        dex_credits = (
            f"This instance is owned {owner_credits} {owner}.\nAn instance of [Ballsdex]"
            f"({settings.github_link}) by El Laggron and maintained by the Ballsdex Team "
            f"and community of [contributors]({settings.github_link}/graphs/contributors)."
        )
        embed.description = (
            f"{' '.join(str(x) for x in balls)}\n"
            f"{settings.about_description}\n"
            f"*Running version **[{ballsdex_version}]({settings.github_link}/releases)***\n"
            f"The bot has been online for **{formatted_uptime}**.\n\n"
            f"**{balls_count:,}** {settings.plural_collectible_name} to collect\n"
            f"**{players_count:,}** players that caught "
            f"**{balls_instances_count:,}** {settings.plural_collectible_name}\n"
            f"**{len(self.bot.guilds):,}** servers playing\n\n"
            f"{dex_credits}\n\n"
            "Consider supporting El Laggron on "
            "[Patreon](https://patreon.com/retke) :heart:\n\n"
            f"[Discord server]({settings.discord_invite}) • [Invite me]({invite_link}) • "
            f"[Source code and issues]({settings.github_link})\n"
            f"[Terms of Service]({settings.terms_of_service}) • "
            f"[Privacy policy]({settings.privacy_policy})"
        )
        v = sys.version_info
        embed.set_footer(
            text=f"Python {v.major}.{v.minor}.{v.micro} • discord.py {discord.__version__}"
        )

        await interaction.response.send_message(embed=embed, view=LicenseInfo())

        view = SectionPaginator(sections, author=interaction.user)
        embed = view.make_embed(view.current_index)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


    @app_commands.command()
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.user.id)
    async def profile(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        Show your collection progressions and currency amounts.
        """
        user_obj = interaction.user
        player_obj, _ = await Player.get_or_create(discord_id=user_obj.id)
        brawler_emoji = self.bot.get_emoji(1372376567153557514)
        skin_emoji = self.bot.get_emoji(1373356124681535582)
        pps_emoji = self.bot.get_emoji(1364817571819425833)
        credits_emoji = self.bot.get_emoji(1364877745032794192)
        starrdrops_emoji = self.bot.get_emoji(1363188571099496699)
        collectibles_emoji = self.bot.get_emoji(1379120934732042240)
        collectible_count = await BallInstance.filter(player=player_obj).count()
        filters = {"player__discord_id": user_obj.id, "ball__enabled": True}
        bot_brawlers = {x: y.emoji_id for x, y in countryballs.items() if y.enabled and 3 <= y.economy_id <= 9 and not 19 <= y.regime_id <= 21 and not y.economy_id == 16}
        bot_skins = {x: y.emoji_id for x, y in countryballs.items() if y.enabled and (22 <= y.regime_id <= 27 or y.regime_id == 35 or 37 <= y.regime_id <= 40)}
        owned_brawlers = set(
            x[0]
            for x in await BallInstance.filter(**filters).exclude(ball__regime_id=19).exclude(ball__regime_id=20).exclude(ball__regime_id=21).exclude(ball__regime_id=22).exclude(ball__regime_id=23).exclude(ball__regime_id=24).exclude(ball__regime_id=25).exclude(ball__regime_id=26).exclude(ball__regime_id=27).exclude(ball__regime_id=28).exclude(ball__regime_id=29).exclude(ball__regime_id=30).exclude(ball__regime_id=31).exclude(ball__regime_id=32).exclude(ball__regime_id=33).exclude(ball__regime_id=35).exclude(ball__regime_id=37).exclude(ball__regime_id=38).exclude(ball__regime_id=39).exclude(ball__regime_id=40)
            .distinct()  # Do not query everything
            .values_list("ball_id")
            )
        owned_skins = set(
            x[0]
            for x in await BallInstance.filter(**filters).exclude(ball__regime_id=5).exclude(ball__regime_id=6).exclude(ball__regime_id=7).exclude(ball__regime_id=8).exclude(ball__regime_id=16).exclude(ball__regime_id=19).exclude(ball__regime_id=20).exclude(ball__regime_id=21).exclude(ball__regime_id=28).exclude(ball__regime_id=29).exclude(ball__regime_id=30).exclude(ball__regime_id=31).exclude(ball__regime_id=32).exclude(ball__regime_id=33).exclude(ball__regime_id=34).exclude(ball__regime_id=36)
            .distinct()  # Do not query everything
            .values_list("ball_id")
            )
        embed = discord.Embed(
            title=f"{user_obj.name}'s Profile",
            color=discord.Colour.from_str("#ffff00")
        )
        embed.set_thumbnail(url=user_obj.display_avatar.url)
        embed.description = (
            f"## Statistics\n"
            f"> {collectible_count}{collectibles_emoji}\n"
            f"> {len(owned_brawlers)}/{len(bot_brawlers)}{brawler_emoji}\n"
            f"> {len(owned_skins)}/{len(bot_skins)}{skin_emoji}\n"
            f"## Resources\n"
            f"> {player_obj.powerpoints}{pps_emoji}\n"
            f"> {player_obj.credits}{credits_emoji}\n"
            f"> {player_obj.sdcount}{starrdrops_emoji}\n"
        )
        await interaction.response.send_message(embed=embed)
