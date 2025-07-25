from __future__ import annotations

import logging
import io
import math
import random
import string
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, cast

import discord
from discord.ui import Button, Modal, TextInput, View
from tortoise.timezone import get_default_timezone
from tortoise.timezone import now as tortoise_now
from tortoise.exceptions import ValidationError

from ballsdex.core.metrics import caught_balls
from ballsdex.core.models import (
    Ball,
    BallInstance,
    Player,
    Special,
    Regime,
    Trade,
    TradeObject,
    balls,
    specials,
)
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.countryballs")


class CountryballNamePrompt(Modal, title=f"Catch this collectible!"):
    name = TextInput(
        label=f"Name of this collectible",
        style=discord.TextStyle.short,
        placeholder="Your guess",
    )

    def __init__(self, view: BallSpawnView, button: Button):
        super().__init__()
        self.view = view
        self.button = button
        self.CollectibleName = view.RegimeName
        self.name.label = f"Name of this {self.CollectibleName}"
        self.title = f"Catch this {self.CollectibleName}!"

    async def on_error(
        self, interaction: discord.Interaction["BallsDexBot"], error: Exception, /  # noqa: W504
    ) -> None:
        log.exception("An error occured in countryball catching prompt", exc_info=error)
        if interaction.response.is_done():
            await interaction.followup.send(
                f"An error occured with this {self.CollectibleName}.",
            )
        else:
            await interaction.response.send_message(
                f"An error occured with this {self.CollectibleName}.",
            )

    async def on_submit(self, interaction: discord.Interaction["BallsDexBot"]):
        if self.view.usertimeout:
            try:
               await interaction.user.timeout(timedelta(seconds=self.view.usertimeout))
               await interaction.response.send_message(f"{interaction.user.mention} GET OUT-\n-# they were timed out for {timedelta(seconds=self.view.usertimeout)}!")
               self.button.disabled = True
               return
            except Exception:
               await interaction.response.send_message(f"{interaction.user.mention} GET OUT-\n-# they couldn't be timeouted.")
               self.button.disabled = True
               return
        await interaction.response.defer(thinking=True)

        player, _ = await Player.get_or_create(discord_id=interaction.user.id)
        if self.view.caught:
            slow_message = random.choice(settings.slow_messages).format(
                user=interaction.user.mention,
                ball=self.view.name,
                regime=self.view.RegimeName,
                Regime=self.view.RegimeName.capitalize(),
                REGIME=self.view.RegimeName.upper(),
                regimes=self.view.RegimeName+"s",
                Regimes=self.view.RegimeName+"s".capitalize(),
                REGIMES=self.view.RegimeName+"s".upper(),
                name=self.view.name,
                Name=self.view.name.capitalize(),
                NAME=self.view.name.upper(),
                names=self.view.name+"s",
                Names=self.view.name+"s".capitalize(),
                NAMES=self.view.name+"s".upper(),
            )

            await interaction.followup.send(
                slow_message,
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions(users=player.can_be_mentioned),
            )
            return

        if not self.view.is_name_valid(self.name.value):
            if len(self.name.value) > 72:
                wrong_name = self.name.value[:72] + ".."
            else:
                wrong_name = self.name.value

            wrong_message = random.choice(settings.wrong_messages).format(
                user=interaction.user.mention,
                ball=self.view.name,
                regime=self.view.RegimeName,
                Regime=self.view.RegimeName.capitalize(),
                REGIME=self.view.RegimeName.upper(),
                regimes=self.view.RegimeName+"s",
                Regimes=self.view.RegimeName+"s".capitalize(),
                REGIMES=self.view.RegimeName+"s".upper(),
                name=self.view.name,
                Name=self.view.name.capitalize(),
                NAME=self.view.name.upper(),
                names=self.view.name+"s",
                Names=self.view.name+"s".capitalize(),
                NAMES=self.view.name+"s".upper(),
                wrong=wrong_name,
            )

            await interaction.followup.send(
                wrong_message,
                allowed_mentions=discord.AllowedMentions(users=player.can_be_mentioned),
                ephemeral=False,
            )
            return

        ball, has_caught_before, dailycatch, fullsd = await self.view.catch_ball(
            interaction.user, player=player, guild=interaction.guild
        )

        await interaction.followup.send(
            self.view.get_catch_message(ball, has_caught_before, interaction.user.mention, dailycatch, fullsd),
            allowed_mentions=discord.AllowedMentions(users=player.can_be_mentioned),
        )
        await interaction.followup.edit_message(self.view.message.id, view=self.view)


class BallSpawnView(View):
    """
    BallSpawnView is a Discord UI view that represents the spawning and interaction logic for a
    countryball in the BallsDex bot. It handles user interactions, spawning mechanics, and
    countryball catching logic.

    Attributes
    ----------
    bot: BallsDexBot
    model: Ball
        The ball being spawned.
    algo: str | None
        The algorithm used for spawning, used for metrics.
    message: discord.Message
        The Discord message associated with this view once created with `spawn`.
    caught: bool
        Whether the countryball has been caught yet.
    ballinstance: BallInstance | None
        If this is set, this ball instance will be spawned instead of creating a new ball instance.
        All properties are preserved, and if successfully caught, the owner is transferred (with
        a trade entry created). Use the `from_existing` constructor to use this.
    special: Special | None
        Force the spawned countryball to have a special event attached. If None, a random one will
        be picked.
    atk_bonus: int | None
        Force a specific attack bonus if set, otherwise random range defined in config.yml.
    hp_bonus: int | None
        Force a specific health bonus if set, otherwise random range defined in config.yml.
    """

    def __init__(self, bot: "BallsDexBot", model: Ball):
        super().__init__()
        self.bot = bot
        self.model = model
        self.algo: str | None = None
        self.message: discord.Message = discord.utils.MISSING
        self.caught = False
        self.ballinstance: BallInstance | None = None
        self.special: Special | None = None
        self.atk_bonus: int | None = None
        self.hp_bonus: int | None = None
        self.RegimeName: str | None = None
        self.fakespawn = False
        self.buttondanger = False
        self.buttontext = None
        self.buttonemoji: discord.Emoji | None = None
        self.usertimeout = False
        self.BlockedList = {}
        self.BlockedTimeout = 10
        self.DontCount = False
        self.voicefile = None

    async def interaction_check(self, interaction: discord.Interaction["BallsDexBot"], /) -> bool:
        return await interaction.client.blacklist_check(interaction)

    async def on_timeout(self):
        self.catch_button.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass
        if self.ballinstance and not self.caught:
            await self.ballinstance.unlock()

    async def catch_button_cb(self, interaction: discord.Interaction["BallsDexBot"]):
         button = self.catch_button
         special_role_map = {
             "Brawl Pass": 1334774634826043433,
             "Brawl Pass Plus": 1335320375948607610,
         }
         special_emoji_map = {
             "Brawl Pass": 1378473792367497236,
             "Brawl Pass Plus": 1378473814182072370
         }
         restricted_server_id = 1295410565145165884
         if interaction.guild and interaction.guild.id == restricted_server_id:
             if self.special:
                 required_role_id = special_role_map.get(self.special.name)
                 self.buttonemoji = interaction.client.get_emoji(special_emoji_map.get(self.special.name))
                 if required_role_id:
                     if isinstance(interaction.user, discord.Member):
                         user_role_ids = {role.id for role in interaction.user.roles}
                         if required_role_id not in user_role_ids:
                             await interaction.response.send_message(f"Only {self.special.name} members can catch this {self.RegimeName}.", ephemeral=True)
                             return
         if self.caught: 
            await interaction.response.send_message("I was caught already!", ephemeral=True)
         elif self.BlockedList.get(interaction.user.id) and self.ball.BlockedList.get(interaction.user.id) > datetime.now(timezone.utc):
            await interaction.response.send_message("I need time to heal", ephemeral=True)
         else:
            await interaction.response.send_modal(CountryballNamePrompt(self, self.catch_button))

    # Wrapper to provide both interaction and button
    async def catch_button_cb_wrapper(self, interaction: discord.Interaction["BallsDexBot"]):
        await BallSpawnView.catch_button_cb(self, interaction)

    @classmethod
    async def from_existing(cls, bot: "BallsDexBot", ball_instance: BallInstance):
        """
        Get an instance from an existing `BallInstance`. Instead of creating a new ball instance,
        this will transfer ownership of the existing instance when caught.

        The ball instance must be unlocked from trades, and will be locked until caught or timed
        out.
        """
        if await ball_instance.is_locked():
            raise RuntimeError("This countryball is locked for a trade")

        # prevent countryball from being traded while spawned
        await ball_instance.lock_for_trade()

        view = cls(bot, ball_instance.countryball)
        view.ballinstance = ball_instance
        return view

    @classmethod
    async def get_random(cls, bot: "BallsDexBot"):
        """
        Get a new instance with a random countryball. Rarity values are taken into account.
        """
        countryballs = list(filter(lambda m: m.enabled, balls.values()))
        if not countryballs:
            raise RuntimeError("No ball to spawn")
        rarities = [x.rarity for x in countryballs]
        cb = random.choices(population=countryballs, weights=rarities, k=1)[0]
        return cls(bot, cb)

    @property
    def name(self):
        return self.model.country

    def get_random_special(self) -> Special | None:
        population = [
            x
            for x in specials.values()
            # handle null start/end dates with infinity times
            if (x.start_date or datetime.min.replace(tzinfo=get_default_timezone()))
            <= tortoise_now()
            <= (x.end_date or datetime.max.replace(tzinfo=get_default_timezone()))
        ]

        if not population:
            return None

        common_weight: float = 1 - sum(x.rarity for x in population)

        if common_weight < 0:
            common_weight = 0

        weights = [x.rarity for x in population] + [common_weight]
        # None is added representing the common countryball
        special: Special | None = random.choices(
            population=population + [None], weights=weights, k=1
        )[0]

        return special

    async def spawn(self, channel: discord.TextChannel) -> bool:
        """
        Spawn a countryball in a channel.

        Parameters
        ----------
        channel: discord.TextChannel
            The channel where to spawn the countryball. Must have permission to send messages
            and upload files as a bot (not through interactions).

        Returns
        -------
        bool
            `True` if the operation succeeded, otherwise `False`. An error will be displayed
            in the logs if that's the case.
        """
        style = discord.ButtonStyle.danger if self.buttondanger else discord.ButtonStyle.primary
        label = self.buttontext or "BRAWL!"
        emoji = self.buttonemoji

        self.catch_button = Button(style=style, label=label, emoji=emoji)
            
        self.catch_button.callback = self.catch_button_cb_wrapper
        self.add_item(self.catch_button)
        
        rid = self.model.regime_id
        if rid == 22 or rid == 23 or rid == 24 or rid == 25 or rid == 26 or rid == 27 or rid == 35 or rid == 37 or rid == 38 or rid == 39 or rid == 40:
            self.RegimeName = "skin"
        elif rid == 28:
            self.RegimeName = "gadget"
        elif rid == 29:
            self.RegimeName = "star power"
        elif rid == 30 or rid == 31 or rid == 32:
            self.RegimeName = "gear"
        elif rid == 33:
            self.RegimeName = "hypercharge"
        else:
            self.RegimeName = "brawler"

        def generate_random_name():
            source = string.ascii_uppercase + string.ascii_lowercase + string.ascii_letters
            return "".join(random.choices(source, k=15))

        ALLOWED_VOICE_EXTENSIONS = [
            "ogg",
            "mp3"
        ]
        extension = self.model.wild_card.split(".")[-1]
        file_location = "./admin_panel/media/" + self.model.wild_card
        file_name = f"nt_{generate_random_name()}.{extension}"
        try:
            permissions = channel.permissions_for(channel.guild.me)
            if permissions.attach_files and permissions.send_messages:
                spawn_message = random.choice(settings.spawn_messages).format(
                    ball=self.name,
                    regime=self.RegimeName,
                    Regime=self.RegimeName.capitalize(),
                    REGIME=self.RegimeName.upper(),
                    regimes=self.RegimeName+"s",
                    Regimes=self.RegimeName+"s".capitalize(),
                    REGIMES=self.RegimeName+"s".upper(),
                    name=self.name,
                    Name=self.name.capitalize(),
                    NAME=self.name.upper(),
                    names=self.name+"s",
                    Names=self.name+"s".capitalize(),
                    NAMES=self.name+"s".upper(),
                )
                if self.voicefile:
                    extension = self.voicefile.filename.split(".")[-1]
                    if extension not in ALLOWED_VOICE_EXTENSIONS:
                        raise ValueError(f"File {self.voicefile.filename}'s extension is not supported.")

                    buffer = io.BytesIO(await self.voicefile.read())  # Assuming it's a discord.Attachment
                    buffer.seek(0)
                    self.message = await channel.send(
                        f"Guess this {self.RegimeName}'s voice to catch them!",
                        view=self,
                        file=discord.File(buffer, filename=f"VOICE_MSG.{extension}"),
                    )
                    return True

                else:
                    self.message = await channel.send(
                        spawn_message,
                        view=self,
                        file=discord.File(file_location, filename=file_name),
                    )
                    return True
            else:
                log.error("Missing permission to spawn ball in channel %s.", channel)
        except discord.Forbidden:
            log.error(f"Missing permission to spawn ball in channel {channel}.")
        except discord.HTTPException:
            log.error("Failed to spawn ball", exc_info=True)
        return False

    def is_name_valid(self, text: str) -> bool:
        """
        Check if the prompted name is valid.

        Parameters
        ----------
        text: str
            The text entered by the user. It will be lowered and stripped of enclosing blank
            characters.

        Returns
        -------
        bool
            Whether the name matches or not.
        """
        if self.model.catch_names:
            possible_names = (self.name.lower(), *self.model.catch_names.split(";"))
        else:
            possible_names = (self.name.lower(),)
        if self.model.translations:
            possible_names += tuple(x.lower() for x in self.model.translations.split(";"))
        cname = text.lower().strip()
        # Remove fancy unicode characters like ’ to replace to '
        cname = cname.replace("\u2019", "'")
        cname = cname.replace("\u2018", "'")
        cname = cname.replace("\u201c", '"')
        cname = cname.replace("\u201d", '"')
        return cname in possible_names

    async def catch_ball(
        self,
        user: discord.User | discord.Member,
        *,
        player: Player | None,
        guild: discord.Guild | None,
    ) -> tuple[BallInstance, bool, int, bool]:
        """
        Mark this countryball as caught and assign a new `BallInstance` (or transfer ownership if
        attribute `ballinstance` was set).

        Parameters
        ----------
        user: discord.User | discord.Member
            The user that will obtain the new countryball.
        player: Player
            If already fetched, add the player model here to avoid an additional query.
        guild: discord.Guild | None
            If caught in a guild, specify here for additional logs. Will be extracted from `user`
            if it's a member object.

        Returns
        -------
        tuple[bool, BallInstance]
            A tuple whose first value indicates if this is the first time this player catches this
            countryball. Second value is the newly created countryball.

            If `ballinstance` was set, this value is returned instead.

        Raises
        ------
        RuntimeError
            The `caught` attribute is already set to `True`. You should always check before calling
            this function that the ball was not caught.
        """
        fullsd = False
        if not self.DontCount:
            try:
                player.dailycaught += 1
            except ValidationError:
                pass
            try:
                sdyes = False
                
                if player.dailycaught in {1, 4, 8}:
                    sdyes = True
                    player.sdcount += 1

                updatef = ["dailycaught",]
                if sdyes:
                    updatef.append("sdcount")
                await player.save(update_fields=updatef)
            except ValidationError:
                fullsd = True

        
        options = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        weights = [5, 4, 5, 10, 8, 7, 8, 9, 10, 7]

        result = random.choices(options, weights=weights, k=1)[0]
        try:
            player.trophies+=result ; await player.save(update_fields=("trophies",))
            Reg = await Regime.get(id=self.model.regime_id)
            if Reg.name.lower().strip().replace(" ", "_") in {"rare", "super_rare", "epic", "mythic", "legendary"}:
                b_trophies = player.brawler_trophies.get(self.model.pk)
                if b_trophies:
                    b_trophies+=result ; await player.save(update_fields=("brawler_trophies",))
        except ValidationError:
            log.debug(f"{user.id} has reached the upper limit of trophies")

        options = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        weights = [1500, 1000, 500, 250, 125, 75, 40, 25, 10, 4, 2] # 1500 being 30% weight and 42.4% chance, 75 being 1.5% weight and 2.1% chance

        result = random.choices(options, weights=weights, k=1)[0]
        bonus_attack = self.atk_bonus or result
        bonus_health = self.hp_bonus or result
        if self.caught:
            raise RuntimeError("This ball was already caught!")
        self.caught = True
        self.catch_button.disabled = True
        player = player or (await Player.get_or_create(discord_id=user.id))[0]
        is_new = not await BallInstance.filter(player=player, ball=self.model).exists()

        if self.ballinstance:
            # if specified, do not create a countryball but switch owner
            # it's important to register this as a trade to avoid bypass
            trade = await Trade.create(player1=self.ballinstance.player, player2=player)
            await TradeObject.create(
                trade=trade, player=self.ballinstance.player, ballinstance=self.ballinstance
            )
            self.ballinstance.trade_player = self.ballinstance.player
            self.ballinstance.player = player
            self.ballinstance.locked = None  # type: ignore
            await self.ballinstance.save(update_fields=("player", "trade_player", "locked"))
            return self.ballinstance, is_new
            

        # check if we can spawn cards with a special background
        special: Special | None = self.special

        if not special:
            special = self.get_random_special()

        if not self.ballinstance:
            mplayer = player
            if self.fakespawn:
                mplayer = await Player.get(discord_id="1294582625352024175")
            ball = await BallInstance.create(
                ball=self.model,
                player=mplayer,
                special=special,
                attack_bonus=bonus_attack,
                health_bonus=bonus_health,
                server_id=guild.id if guild else None,
                spawned_time=self.message.created_at,
            )

        # logging and stats
        log.log(
            logging.INFO if user.id in self.bot.catch_log else logging.DEBUG,
            f"{user} caught {settings.collectible_name} {self.model}, {special=}",
        )
        if isinstance(user, discord.Member) and user.guild.member_count:
            caught_balls.labels(
                country=self.name,
                special=special,
                # observe the size of the server, rounded to the nearest power of 10
                guild_size=10 ** math.ceil(math.log(max(user.guild.member_count - 1, 1), 10)),
                spawn_algo=self.algo,
            ).inc()

        return ball, is_new, player.dailycaught, fullsd

    def get_catch_message(self, ball: BallInstance, new_ball: bool, mention: str, dailycatch: int, fullsd: bool) -> str:
        """
        Generate a user-facing message after a ball has been caught.

        Parameters
        ----------
        ball: BallInstance
            The newly created ball instance
        new_ball: bool
            Boolean indicating if this is a new countryball in completion
            (as returned by `catch_ball`)
        """
        text = ""
        new_cb_emoji = self.bot.get_emoji(1387510759671595058)
        plevel_emojis=[
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
        plevel_emoji = self.bot.get_emoji(plevel_emojis[int(((ball.attack_bonus + 10) / 10))-1])
        if ball.specialcard and ball.specialcard.catch_phrase:
            formatted_special_catch = ball.specialcard.catch_phrase.replace("Regime", self.RegimeName.capitalize())
            text += f"*{formatted_special_catch}*\n"
        if new_ball:
            text += (
                f"{new_cb_emoji} You unlocked a **new {self.RegimeName}**! "
                 f"It's now in your {self.RegimeName} collection! {new_cb_emoji}\n"
            )
        if dailycatch in {1, 4, 8}:
                mj = self.bot.get_emoji(1379137569564000417) if fullsd else self.bot.get_emoji(1363188571099496699)
                pf = "th"
                if dailycatch == 1:
                    pf = "st"
                ut = f"! {mj}"
                if fullsd:
                    ut = f", but Starr Drop limit of 50 was reached, use `/starrdrop` to make space for new Starr Drops. {mj}"
                text += f"{mj} Since this is your {dailycatch}{pf} daily catch, You gained a Starr Drop{ut}"

        caught_message = (
            random.choice(settings.caught_messages).format(
                user=mention,
                wiki_link=f"https://brawldex.fandom.com/wiki/{self.name.replace(" ", "_")}",
                collectible_emoji=self.bot.get_emoji(ball.ball.emoji_id),
                gun_emoji=self.bot.get_emoji(1367203443349000374),
                ball=self.name,
                regime=self.RegimeName,
                Regime=self.RegimeName.capitalize(),
                REGIME=self.RegimeName.upper(),
                regimes=self.RegimeName+"s",
                Regimes=self.RegimeName+"s".capitalize(),
                REGIMES=self.RegimeName+"s".upper(),
                name=self.name,
                Name=self.name.capitalize(),
                NAME=self.name.upper(),
                names=self.name+"s",
                Names=self.name+"s".capitalize(),
                NAMES=self.name+"s".upper(),
            )
            + " "
        )

        return (
            caught_message
            + f"{plevel_emoji} (`#{ball.pk:0X}`)\n\n{text}"
        )
