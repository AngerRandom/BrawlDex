import io
from typing import TYPE_CHECKING
import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast, Tuple

import discord
from discord import app_commands
from discord.ext import commands
from ballsdex.core.utils.logging import log_action
from tortoise.exceptions import BaseORMException, DoesNotExist
from ballsdex.packages.admin.balls import save_file
from ballsdex.packages.staff.cardmaker import merge_images
from ballsdex.packages.staff.cardgenerator import CardGenerator
# from ballsdex.packages.staff.customcard import CardConfig, draw_card
from ballsdex.settings import settings
from ballsdex.core.utils.transformers import BallTransform, SpecialTransform
from ballsdex.core.models import Ball, Special, Player

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.staff")

async def asset_dump(self, brawler: Ball) -> Tuple[str, str, bool, bool, str, str, int, int, int, str, str, str, str, str, str, str]:
    await brawler.fetch_related("regime", "economy")
    return brawler.country, brawler.short_name, brawler.enabled, brawler.tradeable, brawler.economy.name, brawler.regime.name, brawler.health, brawler.attack, brawler.emoji_id, brawler.capacity_name, brawler.capacity_description, brawler.catch_names, f"https://brawldex.fandom.com/wiki/{brawler.country.replace(" ", "_")}", f"https://cdn.discordapp.com/emojis/{brawler.emoji_id}.png", brawler.wild_card, brawler.collection_card 

@app_commands.guilds(*settings.admin_guild_ids)
class Staff(commands.GroupCog, group_name="staff"):
    """
    Staff commands.
    """
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    @app_commands.command(name="cardart", description="Create a card art by merging a background and an image.")
    @app_commands.checks.has_any_role(*settings.root_role_ids, 1357857303222816859)
    async def makecard(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        background: discord.Attachment,
        image: discord.Attachment
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            # Validate content types
            if not background.content_type.startswith("image") or not image.content_type.startswith("image"):
                await interaction.followup.send("Both attachments must be image files (e.g., PNG, JPG).", ephemeral=True)
                return

            # Optional: File size limits (Discord caps at 25 MB normally)
            if background.size > 10 * 1024 * 1024 or image.size > 10 * 1024 * 1024:
                await interaction.followup.send("Each image must be under 10 MB.", ephemeral=True)
                return

            # Merge and send
            result_image = await merge_images(background, image)
            file = discord.File(result_image, filename="card.png")

            await interaction.followup.send(content="Here's your generated card:", file=file, ephemeral=False)

        except Exception as e:
            log.error(f"Error in makecardart: {e}")
            await interaction.followup.send("Something went wrong while processing the images.", ephemeral=True)
    
    @app_commands.command(name="viewcard", description="View a card of an existing brawler/skin.")
    @app_commands.describe(brawler="The brawler/skin to view card of")
    @app_commands.describe(special="The special to apply")
    @app_commands.checks.has_any_role(*settings.root_role_ids, 1357857303222816859)
    async def viewcard(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        brawler: BallTransform,
        special: SpecialTransform | None = None
    ):
        generator = CardGenerator(brawler, special)
        generator.special = special
        image, _ = generator.generate_image()

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

    # Send it as a Discord file
        discord_file = discord.File(fp=buffer, filename="card.png")
        try:
            await interaction.response.send_message(file=discord_file, ephemeral=True)
        except Exception as e:
            log.error("Something went wrong.", exc_info=e)
            await interaction.response.send_message("Something went wrong.", ephemeral=True)

    @app_commands.command()
    @app_commands.checks.has_any_role(*settings.root_role_ids, 1357857303222816859)
    @app_commands.choices(type=[
        app_commands.Choice(name="Wild Art", value="wild"),
        app_commands.Choice(name="Card Art", value="card")
        ])
    async def uploadcard(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        brawler: BallTransform,
        image: discord.Attachment,
        type: app_commands.Choice[str]
        ):
        """
        Update an image asset for a brawler/skin.

        Parameters
        ----------
        brawler: Ball
           The brawler/skin to update its asset
        image: discord.Attachment
            The image to use as the new asset
        type: app_commands.Choice[str]
            Type of the asset (Wild/Card).
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            card_path = await save_file(image)
        except Exception as e:
            await interaction.followup.send("Failed to upload the asset.", ephemeral=True)
            log.exception("Failed to upload the asset", exc_info=True)
            return

        try:
            if type.value.lower() == "wild":
                brawler.wild_card = "/" + str(card_path)
            elif type.value.lower() == "card":
                brawler.collection_card = "/" + str(card_path)
            else:
                await interaction.followup.send("Invalid asset type provided.", ephemeral=True)
                return

            await brawler.save()
            await interaction.followup.send("Asset upload successful.", ephemeral=True)
            await log_action(f"{interaction.user} updated {brawler.country}'s card asset.", interaction.client)
            await interaction.client.load_cache()
        except BaseORMException as e:
            await interaction.followup.send("Failed to update the brawler.", ephemeral=True)
            log.exception("Failed to update the brawler", exc_info=True)
        
    @app_commands.command()
    @app_commands.checks.has_any_role(*settings.root_role_ids, 1357857303222816859)
    @app_commands.choices(type=[
        app_commands.Choice(name="Title", value="title"),
        app_commands.Choice(name="Text", value="text"),
        app_commands.Choice(name="Credits", value="credits")
        ])
    async def uploadtext(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        brawler: BallTransform,
        text: str,
        type: app_commands.Choice[str]
        ):
        """
        Update a text asset for a brawler/skin.

        Parameters
        ----------
        brawler: Ball
            The brawler/skin to update its asset.
        text: str
            The text to use as the new asset.
        type: app_commands.Choice[str]
            Type of the asset (Title/Text/Credits).
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if type.value.lower() == "title":
                brawler.capacity_name = text
            elif type.value.lower() == "text":
                brawler.capacity_description = text
            elif type.value.lower() == "credits":
                brawler.credits = text
            else:
                await interaction.followup.send("Invalid asset type provided.", ephemeral=True)
                return

            await brawler.save()
            await interaction.followup.send("Text update successful.", ephemeral=True)
            await log_action(f"{interaction.user} updated {brawler.country}'s text asset.", interaction.client)
            await interaction.client.load_cache()
        except BaseORMException as e:
            await interaction.followup.send("Failed to update the brawler.", ephemeral=True)
            log.exception("Failed to update the brawler", exc_info=True)
            
    @app_commands.command(name="currency", description="Give some currency to a user!")
    @app_commands.checks.has_any_role(*settings.root_role_ids, 1357857303222816859)
    @app_commands.choices(currency_type=[
        app_commands.Choice(name="Power Points", value="powerpoints"),
        app_commands.Choice(name="Credits", value="credits"),
        app_commands.Choice(name="Starr Drops", value="starrdrops")
        ])
    @app_commands.describe(currency_type="The currency type to give")
    @app_commands.describe(user="The target user to give a currency")
    @app_commands.describe(amount="Amount of currencies to give")
    @app_commands.describe(remove="If enabled, the command will remove the currency instead.")
    async def currency(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        currency_type: app_commands.Choice[str],
        user: discord.User,
        amount: int,
        remove: bool | None = None
        ):
            player, _ = await Player.get_or_create(discord_id=user.id)
            pp_emoji = interaction.client.get_emoji(1364817571819425833)
            credit_emoji = interaction.client.get_emoji(1364877745032794192)
            sd_emoji = interaction.client.get_emoji(1363188571099496699)
            if amount <= 0:
                await interaction.response.send_message("You can't add/remove less than or equal to zero amount!", ephemeral=True)
                return
            if type(amount) == "float":
                await interaction.response.send_mesaage("The amount must be an integer, not a float!", ephemeral=True)
                return
            if remove and remove == True:
                if currency_type.value == "powerpoints":
                    try:
                        player.powerpoints -= amount
                        await player.save()
                        await interaction.response.send_message(f"{interaction.user.mention} removed {amount} Power Points from {user.mention}! {pp_emoji}", ephemeral=False)
                        await log_action(f"{interaction.user.name} removed {amount} Power Points from {user.name}.", interaction.client)
                    except Exception as e:
                        log.error("An error occured while removing currency.", exc_info=e)
                        return
                elif currency_type.value == "credits":
                    try:
                        player.credits -= amount
                        await player.save()
                        await interaction.response.send_message(f"{interaction.user.mention} removed {amount} Credits from {user.mention}! {credit_emoji}", ephemeral=False)
                        await log_action(f"{interaction.user.name} removed {amount} Credits from {user.name}.", interaction.client)
                    except Exception as e:
                        log.error("An error occured while removing currency.", exc_info=e)
                        return
                elif currency_type.value == "starrdrops":
                    try:
                        player.sdcount -= amount
                        await player.save()
                        await interaction.response.send_message(f"{interaction.user.mention} removed {amount} Starr Drops from {user.mention}! {sd_emoji}", ephemeral=False)
                        await log_action(f"{interaction.user.name} removed {amount} Starr Drops from {user.name}.", interaction.client)
                    except Exception as e:
                        log.error("An error occured while removing currency.", exc_info=e)
                        return
            else:
                if currency_type.value == "powerpoints":
                    try:
                        player.powerpoints += amount
                        await player.save()
                        await interaction.response.send_message(f"{interaction.user.mention} gave {amount} Power Points to {user.mention}! {pp_emoji}", ephemeral=False)
                        await log_action(f"{interaction.user.name} gave {amount} Power Points to {user.name}.", interaction.client)
                    except Exception as e:
                        log.error("An error occured while adding currency.", exc_info=e)
                        return
                elif currency_type.value == "credits":
                    try:
                        player.credits += amount
                        await player.save()
                        await interaction.response.send_message(f"{interaction.user.mention} gave {amount} Credits to {user.mention}! {credit_emoji}", ephemeral=False)
                        await log_action(f"{interaction.user.name} gave {amount} Credits to {user.name}.", interaction.client)
                    except Exception as e:
                        log.error("An error occured while adding currency.", exc_info=e)
                        return
                elif currency_type.value == "starrdrops":
                    if amount > 50:
                        await interaction.response.send_message("The amount can't exceed 50 Starr Drops!", ephemeral=True)
                        return
                    elif amount + player.sdcount > 50:
                        await interaction.response.send_message(f"This user has {player.sdcount} Starr Drops. The amount you tried to give will exceed the limit. {f"It is recommended to give {50-player.sdcount} Starr Drops maximum to reach the limit instead." if player.sdcount < 50 else "You can't give more drops until they uses them."}", ephemeral=True)
                        return
                    else:
                        try:
                            player.sdcount += amount
                            await player.save()
                            await interaction.response.send_message(f"{interaction.user.mention} gave {amount} Starr Drops to {user.mention}! {sd_emoji}", ephemeral=False)
                            await log_action(f"{interaction.user.name} gave {amount} Starr Drops to {user.name}.", interaction.client)
                        except Exception as e:
                            log.error("An error occured while adding currency.", exc_info=e)
                            return

    @app_commands.command(name="assets", description="Fetch all assets of the brawler/skin!")
    @app_commands.checks.has_any_role(*settings.root_role_ids, 1357857303222816859)
    @app_commands.describe(brawler="The brawler/skin to fetch its assets")
    async def fetch_assets(self, interaction: discord.Interaction["BallsDexBot"], brawler: BallTransform):
        try:
            name, shortname, enabled, tradeable, economy, regime, health, attack, pin, title, cardtext, catchnames, wikilink, pinlink, wildart, cardart = await asset_dump(self, brawler)
            filearray = []
            wildfile = discord.File(wildart)
            cardfile = discord.File(cardart)
            filearray.append(wildfile)
            filearray.append(cardfile)
            await interaction.response.send_message(
                f"Name: `{name}`\n"
                f"Short Name: `{shortname}`\n"
                f"Enabled: `{"Yes" if enabled == True else "No"}`\n"
                f"Tradeable: `{"Yes" if tradeable == True else "No"}`\n"
                f"Economy: `{economy}`\n"
                f"Regime: `{regime}`\n"
                f"Health: `{health}`\n"
                f"Attack: `{attack}`\n"
                f"Pin: `{pin}`\n"
                f"Title: `{title}`\n"
                f"Card Text: `{cardtext}`\n"
                f"Catch Names: `{catchnames}`\n"
                f"Wiki Link: {wikilink}\n"
                f"Pin Link: {pinlink}",
                files=filearray,
                ephemeral=False
            )
        except Exception as e:
            log.error("Something went wrong in asset dump.", exc_info=e)
            return
                
   
                    
        
  #  @app_commands.command(name="customcard", description="Generate a custom card with your own assets!")
  #  @app_commands.checks.has_any_role(*settings.root_role_ids, 1357857303222816859)
  #  @app_commands.describe(name="The name of the card character")
  #  @app_commands.describe(title="The ability title of the card character")
  #  @app_commands.describe(text="The ability text of the card character")
  #  @app_commands.describe(health="The health of the card character")
  #  @app_commands.describe(attack="The attack of the card character")
  #  @app_commands.describe(background="The background of the card (1428x2000)")
  #  @app_commands.describe(economy="The economy icon of the card (Max 512x512)")
  #  @app_commands.describe(artwork="The artwork of the card character (1360x730)")
  #  @app_commands.describe(special="Special to apply to the card")
  #  async def customcard(
  #      self,
  #      interaction: discord.Interaction["BallsDexBot"],
  #      name: str,
  #      title: str,
  #      text: str,
  #      health: int,
  #      attack: int,
  #      background: discord.Attachment,
  #      economy: discord.Attachment,
  #      artwork: discord.Attachment,
  #      special: SpecialTransform | None = None,
  #  ):
  #      config = CardConfig(
  #          ball_name=name,
  #          capacity_name=title,
  #          capacity_description=text,
  #          health=health,
  #          attack=attack,
  #          collection_card=artwork,
  #          background=background,
  #          economy_icon=economy,
  #          special_card=special if special else None,
  #          ball_credits=f"Card generation made by the {settings.bot_name} bot",
  #      )
        
