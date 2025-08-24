from typing import TYPE_CHECKING, Optional, cast

import discord
from discord import app_commands
from discord.ext import commands

from ballsdex.core.models import GuildConfig
from ballsdex.packages.config.components import AcceptTOSView
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

activation_embed = discord.Embed(
    colour=0x00D936,
    title=f"BrawlDex Spawn Activation",
    description="After pressing \"Accept\" Brawlers & Skins will start appearing in this channel, here's some infos:\n* Brawlers/Skins will spawn based on how active the server is, which can be every 20 minutes or every few hours if the server is not very active.\n* When a Brawler appears you have 3 minutes to click \"BRAWL!\", to defeat and obtain the Brawler you must write their name correctly, if not defeated for 3 minutes the Brawler will run away.\n* We have a wiki named [brawldex.fandom.com](<https://brawldex.fandom.com/wiki/BrawlDex_Wiki>) that you can visit to learn more about the bot.\n* You can [click this to join our server](https://discord.gg/brawldex) to ask [questions](https://discord.com/channels/1295410565145165884/1373283076272164895) or to [submit your art](https://discord.com/channels/1295410565145165884/1331358375002243122) to bot, all the art and card texts were submitted by peoples like you.\n* This bot is not affiliated with, endorsed, sponsored, or specifically approved by Supercell and Supercell is not responsible for it. For more information see [Supercell's Fan Content Policy](https://www.supercell.com/fan-content-policy).\nBy pressing \"Accept\" the server accepts to follow our Terms of Service and Privacy Policy.",
    )


@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
class Config(commands.GroupCog):
    """
    View and manage your countryballs collection.
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    @app_commands.command()
    @app_commands.describe(silent="Whether to hide wrong/caught messages or not")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(
        read_messages=True,
        send_messages=True,
        embed_links=True,
    )
    async def channel(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        channel: Optional[discord.TextChannel] = None,
        silent: bool = False,
    ):
        """
        Set or change the channel where countryballs will spawn.

        Parameters
        ----------
        channel: discord.TextChannel
            The channel you want to set, current one if not specified.
        """
        user = cast(discord.Member, interaction.user)

        if channel is None:
            if isinstance(interaction.channel, discord.TextChannel):
                channel = interaction.channel
            else:
                await interaction.response.send_message(
                    "The current channel is not a valid text channel.", ephemeral=True
                )
                return

        view = AcceptTOSView(interaction, channel, user)
        embed = activation_embed.copy()

        guild = interaction.guild
        assert guild
        readable_channels = len(
            [x for x in guild.text_channels if x.permissions_for(guild.me).read_messages]
        )
        if readable_channels / len(guild.text_channels) < 0.75:
            embed.add_field(
                name="\N{WARNING SIGN}\N{VARIATION SELECTOR-16} Warning",
                value=f"This server has {len(guild.text_channels)} channels, but "
                f"{settings.bot_name} can only read {readable_channels} channels.\n"
                "Spawn is based on message activity, too few readable channels will result in "
                "fewer spawns. It is recommended that you inspect your permissions.",
            )
        message = await channel.send(embed=embed, view=view)
        view.message = message

        await interaction.response.send_message(
            f"The activation embed has been sent in {channel.mention}.", ephemeral=True
        )

    @app_commands.command()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(send_messages=True)
    async def disable(self, interaction: discord.Interaction["BallsDexBot"]):
        """
        Disable or enable countryballs spawning.
        """
        guild = cast(discord.Guild, interaction.guild)  # guild-only command
        config, created = await GuildConfig.get_or_create(guild_id=interaction.guild_id)
        if config.enabled:
            config.enabled = False  # type: ignore
            await config.save()
            self.bot.dispatch("ballsdex_settings_change", guild, enabled=False)
            await interaction.response.send_message(
                f"{settings.bot_name} is now disabled in this server. Commands will still be "
                f"available, but the spawn of new {settings.plural_collectible_name} "
                "is suspended.\nTo re-enable the spawn, use the same command."
            )
        else:
            config.enabled = True  # type: ignore
            await config.save()
            self.bot.dispatch("ballsdex_settings_change", guild, enabled=True)
            if config.spawn_channel and (channel := guild.get_channel(config.spawn_channel)):
                if channel:
                    await interaction.response.send_message(
                        f"{settings.bot_name} is now enabled in this server, "
                        f"{settings.plural_collectible_name} will start spawning "
                        f"soon in {channel.mention}."
                    )
                else:
                    await interaction.response.send_message(
                        "The spawning channel specified in the configuration is not available.",
                        ephemeral=True,
                    )
            else:
                await interaction.response.send_message(
                    f"{settings.bot_name} is now enabled in this server, however there is no "
                    "spawning channel set. Please configure one with `/config channel`."
                )
