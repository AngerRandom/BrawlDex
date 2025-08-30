from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from enum import IntEnum
from io import BytesIO
from typing import TYPE_CHECKING, Iterable, Tuple, Type

import discord
from discord.utils import format_dt
from tortoise import exceptions, fields, models, signals, timezone, validators
from tortoise.contrib.postgres.indexes import PostgreSQLIndex
from tortoise.expressions import Q

from ballsdex.core.image_generator.image_gen import draw_card
from ballsdex.settings import settings

if TYPE_CHECKING:
    from tortoise.backends.base.client import BaseDBAsyncClient

    from ballsdex.core.bot import BallsDexBot


balls: dict[int, Ball] = {}
regimes: dict[int, Regime] = {}
economies: dict[int, Economy] = {}
specials: dict[int, Special] = {}

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
FANMADE_SKINS = [
    157,
    156,
    211,
    318,
    320,
    321,
    322,
    337,
    338,
    324,
    336,
    342,
    343,
    361,
    346,
    363,
    364,
    365,
    366,
    370,
    371,
    372,
    373,
    383,
    393,
    411
]
CHINA_SKINS = [
    220,
    248,
    252,
    267,
    282,
    283,
    284,
    285,
    295
]
PRO_SKIN_REGIMES = [
    38,
    39,
    40
]
CHINA_SKIN_REGIMES = [
    37
]
RARITY_EMOJIS = {
    "Rare": 1330493249235714189,
    "Super Rare": 1330493410884456528,
    "Epic": 1330493427011555460,
    "Mythic": 1330493448469483580,
    "Legendary": 1330493465221529713,
    "Ultra Legendary": 1368271368382320761,
    "Rare Skin": 1329613491216322613,
    "Super Rare Skin": 1329613550746075178,
    "Epic Skin": 1329613562376622122,
    "Mythic Skin": 1329613573843980378,
    "Legendary Skin": 1329613584644182048,
    "Ultimate Skin": 1374258318297665556,
    "Hypercharge Skin": 1329613598720393337,
    "Super Pro Skin": 1329613550746075178,
    "Mythic Pro Skin": 1329613573843980378,
    "Hyper Pro Skin": 1329613598720393337
}
FAME_SPECIALS = [
    9,
    10,
    11,
    12,
    13,
    14,
    15
]
async def lower_catch_names(
    model: Type[Ball],
    instance: Ball,
    created: bool,
    using_db: "BaseDBAsyncClient | None" = None,
    update_fields: Iterable[str] | None = None,
):
    if instance.catch_names:
        instance.catch_names = ";".join(
            [x.strip() for x in instance.catch_names.split(";")]
        ).lower()


async def lower_translations(
    model: Type[Ball],
    instance: Ball,
    created: bool,
    using_db: "BaseDBAsyncClient | None" = None,
    update_fields: Iterable[str] | None = None,
):
    if instance.translations:
        instance.translations = ";".join(
            [x.strip() for x in instance.translations.split(";")]
        ).lower()


class DiscordSnowflakeValidator(validators.Validator):
    def __call__(self, value: int):
        if not 17 <= len(str(value)) <= 19:
            raise exceptions.ValidationError("Discord IDs are between 17 and 19 characters long")

class GuildConfig(models.Model):
    guild_id = fields.BigIntField(
        description="Discord guild ID", unique=True, validators=[DiscordSnowflakeValidator()]
    )
    spawn_channel = fields.BigIntField(
        description="Discord channel ID where balls will spawn", null=True
    )
    enabled = fields.BooleanField(
        description="Whether the bot will spawn countryballs in this guild", default=True
    )
    # this option is currently disabled
    silent = fields.BooleanField(
        description="Whether the responses of guesses get sent as ephemeral or not",
        default=False,
    )
    chinese_skin_toggle = fields.BooleanField(
        description="Whether to allow spawning Chinese skins spawning.",
        default=False
    )
    fanmade_skin_toggle = fields.BooleanField(
        description="Whether to allow spawning Fanmade skins spawning.",
        default=False
    )
    fanmade_brawler_toggle = fields.BooleanField(
        description="Whether to allow spawning Fanmade brawlers spawning.",
        default=False
    )

class Regime(models.Model):
    name = fields.CharField(max_length=64)
    background = fields.CharField(max_length=200, description="1428x2000 PNG image")

    def __str__(self):
        return self.name


class Economy(models.Model):
    name = fields.CharField(max_length=64)
    icon = fields.CharField(max_length=200, description="512x512 PNG image")
    emoji = fields.BigIntField(
        description="Emoji ID for this economy", 
        validators=[DiscordSnowflakeValidator()],
        null=True,
    )

    def __str__(self):
        return self.name


class Special(models.Model):
    name = fields.CharField(max_length=64)
    catch_phrase = fields.CharField(
        max_length=512,
        description="Sentence sent in bonus when someone catches a special card",
        null=True,
        default=None,
    )
    start_date = fields.DatetimeField(null=True, default=None)
    end_date = fields.DatetimeField(null=True, default=None)
    rarity = fields.FloatField(
        description="Value between 0 and 1, chances of using this special background."
    )
    background = fields.CharField(max_length=200, description="1428x2000 PNG image", null=True)
    emoji = fields.CharField(
        max_length=20,
        description="Either a unicode character or a discord emoji ID",
        null=True,
    )
    tradeable = fields.BooleanField(default=True)
    hidden = fields.BooleanField(default=False, description="Hides the event from user commands")
    credits = fields.CharField(
        max_length=64, description="Author of the special event artwork", null=True
    )

    def __str__(self) -> str:
        return self.name

class ItemType(IntEnum):
    TEST = 0
    BRAWLER = 1
    SKIN = 2
    FANMADE_BRAWLER = 3
    FANMADE_SKIN = 4
    CHINA_SKIN = 5
    PRO_SKIN = 6
    LIMITED_BRAWLER = 7
    LIMITED_SKIN = 8
    SILVER_TITLE = 9
    GOLDEN_TITLE = 10
    BLING_TITLE = 11
    

class Ball(models.Model):
    regime_id: int
    economy_id: int

    country = fields.CharField(max_length=48, unique=True, description="Name of this countryball")
    short_name = fields.CharField(
        max_length=24,
        null=True,
        default=None,
        description="Alternative shorter name to be used in card design, "
        "12 characters max, optional",
    )
    catch_names = fields.TextField(
        null=True,
        default=None,
        description="Additional possible names for catching this ball, separated by semicolons",
    )
    translations = fields.TextField(
        null=True,
        default=None,
        description="Translations for the country name, separated by semicolons",
    )
    regime: fields.ForeignKeyRelation[Regime] = fields.ForeignKeyField(
        "models.Regime", description="Political regime of this country", on_delete=fields.CASCADE
    )
    economy: fields.ForeignKeyRelation[Economy] | None = fields.ForeignKeyField(
        "models.Economy",
        description="Economical regime of this country",
        on_delete=fields.SET_NULL,
        null=True,
    )
    item_type = fields.IntEnumField(
        ItemType,
        description="The type of the item",
        default=ItemType.BRAWLER
    )
    health = fields.IntField(description="Ball health stat")
    attack = fields.IntField(description="Ball attack stat")
    rarity = fields.FloatField(
        description="Rarity of this ball. "
        "Higher number means more likely to spawn, 0 is unspawnable."
    )
    enabled = fields.BooleanField(
        default=True, description="Disabled balls will never spawn or show up in completion."
    )
    tradeable = fields.BooleanField(
        default=True, description="Controls whether this ball can be traded or donated."
    )
    is_new = fields.BooleanField(
        default=False,
        description="Whether it's a new ball added"
    )
    emoji_id = fields.BigIntField(
        description="Emoji ID for this ball", validators=[DiscordSnowflakeValidator()]
    )
    wild_card = fields.CharField(
        max_length=200, description="Image used when a new ball spawns in the wild"
    )
    collection_card = fields.CharField(
        max_length=200, description="Image used when displaying balls"
    )
    credits = fields.CharField(max_length=256, description="Author of the collection artwork")
    capacity_name = fields.CharField(
        max_length=64, description="Name of the countryball's ability"
    )
    capacity_description = fields.CharField(
        max_length=256, description="Description of the countryball's ability"
    )
    capacity_logic = fields.JSONField(description="Effect of this capacity", default={})
    created_at = fields.DatetimeField(auto_now_add=True, null=True)

    instances: fields.BackwardFKRelation[BallInstance]

    def __str__(self) -> str:
        return self.country

    @property
    def cached_regime(self) -> Regime:
        return regimes.get(self.regime_id, self.regime)

    @property
    def cached_economy(self) -> Economy | None:
        return economies.get(self.economy_id, self.economy)


Ball.register_listener(signals.Signals.pre_save, lower_catch_names)
Ball.register_listener(signals.Signals.pre_save, lower_translations)


class BallInstance(models.Model):
    ball_id: int
    special_id: int
    trade_player_id: int

    ball: fields.ForeignKeyRelation[Ball] = fields.ForeignKeyField("models.Ball")
    player: fields.ForeignKeyRelation[Player] = fields.ForeignKeyRelation(
        "models.Player", related_name="balls"
    )  # type: ignore
    catch_date = fields.DatetimeField(auto_now_add=True)
    spawned_time = fields.DatetimeField(null=True)
    server_id = fields.BigIntField(
        description="Discord server ID where this ball was caught", null=True
    )
    special: fields.ForeignKeyRelation[Special] | None = fields.ForeignKeyField(
        "models.Special", null=True, default=None, on_delete=fields.SET_NULL
    )
    health_bonus = fields.IntField(default=0)
    attack_bonus = fields.IntField(default=0)
    trade_player: fields.ForeignKeyRelation[Player] | None = fields.ForeignKeyField(
        "models.Player", null=True, default=None, on_delete=fields.SET_NULL
    )
    favorite = fields.BooleanField(default=False)
    tradeable = fields.BooleanField(default=True)
    locked: fields.Field[datetime] = fields.DatetimeField(
        description="If the instance was locked for a trade and when",
        null=True,
        default=None,
    )
    extra_data = fields.JSONField(default={})

    class Meta:
        unique_together = ("player", "id")
        indexes = [
            PostgreSQLIndex(fields=("ball_id",)),
            PostgreSQLIndex(fields=("player_id",)),
            PostgreSQLIndex(fields=("special_id",)),
        ]

    @property
    def is_tradeable(self) -> bool:
        return (
            self.tradeable
            and self.countryball.tradeable
            and getattr(self.specialcard, "tradeable", True)
        )

    @property
    def attack(self) -> int:
        bonus = int(self.countryball.attack * self.attack_bonus * 0.01)
        return self.countryball.attack + bonus

    @property
    def health(self) -> int:
        bonus = int(self.countryball.health * self.health_bonus * 0.01)
        return self.countryball.health + bonus

    @property
    def special_card(self) -> str | None:
        if self.specialcard:
            return self.specialcard.background or self.countryball.collection_card

    @property
    def countryball(self) -> Ball:
        return balls.get(self.ball_id, self.ball)

    @property
    def specialcard(self) -> Special | None:
        return specials.get(self.special_id, self.special)

    def __str__(self) -> str:
        return self.to_string()

    def to_string(self, bot: discord.Client | None = None, is_trade: bool = False) -> str:
        emotes = ""
        if bot and self.pk in bot.locked_balls and not is_trade:  # type: ignore
            emotes += "🔒"
        if self.favorite and not is_trade:
            emotes += settings.favorited_collectible_emoji
        if emotes:
            emotes += " "
        if self.specialcard:
            emotes += self.special_emoji(bot)
        country = (
            self.countryball.country
            if isinstance(self.countryball, Ball)
            else f"<Ball {self.ball_id}>"
        )
        return f"{emotes}#{self.pk:0X} {country}"

    def special_emoji(self, bot: discord.Client | None, use_custom_emoji: bool = True) -> str:
        if self.specialcard:
            if not use_custom_emoji:
                return "⚡ "
            special_emoji = ""
            try:
                emoji_id = int(self.specialcard.emoji)
                special_emoji = bot.get_emoji(emoji_id) if bot else "⚡ "
            except ValueError:
                special_emoji = self.specialcard.emoji
            except TypeError:
                return ""
            if special_emoji:
                return f"{special_emoji} "
        return ""

    def description(
        self,
        *,
        short: bool = False,
        include_emoji: bool = False,
        bot: discord.Client | None = None,
        is_trade: bool = False,
    ) -> str:
        text = self.to_string(bot, is_trade=is_trade)
        if "Buzz Lightyear" in self.countryball.country:
                descplevel = "∞"
        elif (
                 not (0 <= self.attack_bonus <= 100) or
                 not (0 <= self.health_bonus <= 100) or
                 self.attack_bonus != self.health_bonus
             ):
                descplevel = "?"
        else:
                descplevel = int((self.attack_bonus + 10) / 10)
        if not short:
            text += f" (Power Level {descplevel})"
        if include_emoji:
            if not bot:
                raise TypeError(
                    "You need to provide the bot argument when using with include_emoji=True"
                )
            if isinstance(self.countryball, Ball):
                emoji = bot.get_emoji(self.countryball.emoji_id)
                if emoji:
                    text = f"{emoji} {text}"
        return text

    def draw_card(self) -> BytesIO:
        image, kwargs = draw_card(self)
        buffer = BytesIO()
        image.save(buffer, **kwargs)
        buffer.seek(0)
        image.close()
        return buffer

    async def prepare_for_message(
        self, interaction: discord.Interaction["BallsDexBot"]
    ) -> Tuple[str, discord.File, discord.ui.View]:
        await self.fetch_related("ball", "special", "trade_player")
        await self.ball.fetch_related("regime", "economy")
        # message content
        trade_content = ""
        await self.fetch_related("trade_player", "special")
        if self.trade_player:
            original_player = None
            # we want to avoid calling fetch_user if possible (heavily rate-limited call)
            if interaction.guild:
                try:
                    original_player = await interaction.guild.fetch_member(
                        int(self.trade_player.discord_id)
                    )
                except discord.NotFound:
                    pass
            elif original_player is None:  # try again if not found in guild
                try:
                    original_player = await interaction.client.fetch_user(
                        int(self.trade_player.discord_id)
                    )
                except discord.NotFound:
                    pass

            original_player_name = (
                original_player.name
                if original_player
                else f"user with ID {self.trade_player.discord_id}"
            )
            trade_content = f"Obtained by trade with {original_player_name}\n"

        special_emoji = ""
        special_name = ""
        special_wiki_link = ""
        formatted_special_text = ""
        rarity_emoji = ""
        skin_type = ""
        new_emoji = ""
        skin_type_emoji = ""
        formatted_second_row = ""
        skin_theme = ""
        skin_theme_emoji = ""
        EXCLUDED_ECONOMIES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16]
        if self.ball.regime.name in RARITY_EMOJIS.keys():
            rarity_emoji = interaction.client.get_emoji(RARITY_EMOJIS.get(self.ball.regime.name))
        if self.countryball.is_new:
            new_emoji = interaction.client.get_emoji(1387510759671595058)
        if self.ball.economy_id not in EXCLUDED_ECONOMIES:
            skin_theme = f"[{self.ball.economy.name}](https://brawldex.fandom.com/wiki/{self.ball.economy.name.replace(" ", "_")})"
            skin_theme_emoji = interaction.client.get_emoji(self.ball.economy.emoji)
        if self.countryball.item_type == ItemType.PRO_SKIN:
            skin_type = "[Pro](<https://brawldex.fandom.com/wiki/Pro>)"
            skin_type_emoji = interaction.client.get_emoji(1385477217269583892)
        elif self.countryball.item_type == ItemType.CHINA_SKIN:
            skin_type = "[China](<https://brawldex.fandom.com/wiki/China>)"
            skin_type_emoji = interaction.client.get_emoji(1372264199174230106)
        elif self.countryball.item_type == ItemType.FANMADE_SKIN or self.countryball.item_type == ItemType.FANMADE_BRAWLER:
            skin_type = "[Fanmade](<https://brawldex.fandom.com/wiki/Fanmade>)"
            skin_type_emoji = interaction.client.get_emoji(1365147307829497967)
        if skin_theme != "":
            formatted_second_row += f"{skin_theme}{skin_theme_emoji} "
            if skin_type != "":
                formatted_second_row += f"({skin_type}{skin_type_emoji})"
            else:
                pass
        if self.specialcard:
            if self.special_id in FAME_SPECIALS:
                special_wiki_link = "https://brawldex.fandom.com/wiki/Fame"
            else:
                special_wiki_link = "https://brawldex.fandom.com/wiki/Specials"
            special_name = f"[{self.specialcard.name}](<{special_wiki_link}>)"
            special_emoji = self.special.emoji
            formatted_special_text = f"({special_name} {special_emoji})"
        emoji = interaction.client.get_emoji(self.countryball.emoji_id)
        plevel = int((self.attack_bonus + 10) / 10)
        if "Buzz Lightyear" in self.countryball.country:
            plevel_emoji = interaction.client.get_emoji(1367815787078877244)
        elif (
                 not (0 <= self.attack_bonus <= 100) or
                 not (0 <= self.health_bonus <= 100) or
                 self.attack_bonus != self.health_bonus
             ):
            plevel_emoji = interaction.client.get_emoji(1366788841549336777)
        else:
            plevel_emoji = interaction.client.get_emoji(plevel_emojis[plevel-1])
        formatted_brawler_name = self.countryball.country
        if " " in self.countryball.country:
            formatted_brawler_name = self.countryball.country.replace(" ", "_")
        if formatted_second_row != "":
            content = (
                f"[{self.countryball.country}](<https://brawldex.fandom.com/wiki/{formatted_brawler_name}>) {emoji}{plevel_emoji}{rarity_emoji}{new_emoji} {formatted_special_text}\n"
                f"{formatted_second_row}\n"
                f"Defeated on {format_dt(self.catch_date)} (`#{self.pk:0X}`)\n"
                f"{trade_content}"
            )
        else:
            content = (
                f"[{self.countryball.country}](<https://brawldex.fandom.com/wiki/{formatted_brawler_name}>) {emoji}{plevel_emoji}{rarity_emoji}{new_emoji} {formatted_special_text}\n"
                f"Defeated on {format_dt(self.catch_date)} (`#{self.pk:0X}`)\n"
                f"{trade_content}"
            )

        # draw image
        with ThreadPoolExecutor() as pool:
            buffer = await interaction.client.loop.run_in_executor(pool, self.draw_card)

        view = discord.ui.View()
        return content, discord.File(buffer, "card.webp"), view

    async def lock_for_trade(self):
        self.locked = timezone.now()
        await self.save(update_fields=("locked",))

    async def unlock(self):
        self.locked = None  # type: ignore
        await self.save(update_fields=("locked",))

    async def is_locked(self):
        await self.refresh_from_db(fields=("locked",))
        self.locked
        return self.locked is not None and (self.locked + timedelta(minutes=30)) > timezone.now()


class DonationPolicy(IntEnum):
    ALWAYS_ACCEPT = 1
    REQUEST_APPROVAL = 2
    ALWAYS_DENY = 3
    FRIENDS_ONLY = 4


class PrivacyPolicy(IntEnum):
    ALLOW = 1
    DENY = 2
    SAME_SERVER = 3
    FRIENDS = 4


class MentionPolicy(IntEnum):
    ALLOW = 1
    DENY = 2


class FriendPolicy(IntEnum):
    ALLOW = 1
    DENY = 2


class TradeCooldownPolicy(IntEnum):
    COOLDOWN = 1
    BYPASS = 2


class Player(models.Model):
    discord_id = fields.BigIntField(
        description="Discord user ID", unique=True, validators=[DiscordSnowflakeValidator()]
    )
    credits = fields.IntField(
    description="User Credits",
    default=0,
    validators=[validators.MaxValueValidator((1 << 63) - 1), validators.MinValueValidator(0)],
    )
    powerpoints = fields.IntField(
    description="User Power Points",
    default=0,
    validators=[validators.MaxValueValidator((1 << 63) - 1), validators.MinValueValidator(0)],
    )
    sdcount = fields.IntField(
    description="Number of Starr Drops the player owns",
    validators=[validators.MaxValueValidator(50), validators.MinValueValidator(0)],
    default=0,
    )
    dailycaught = fields.IntField(
    description="Daily Caught Brawlers",
    index=True,
    validators=[validators.MaxValueValidator(1000), validators.MinValueValidator(0)],
    default=0,
    )
    trophies = fields.IntField(
    description="User Trophies",
    default=0,
    index=True,
    validators=[validators.MaxValueValidator((1 << 63) - 1), validators.MinValueValidator(0)],
    )
    brawler_trophies = fields.JSONField(default={}, null=True)
    donation_policy = fields.IntEnumField(
        DonationPolicy,
        description="How you want to handle donations",
        default=DonationPolicy.ALWAYS_ACCEPT,
    )
    privacy_policy = fields.IntEnumField(
        PrivacyPolicy,
        description="How you want to handle privacy",
        default=PrivacyPolicy.DENY,
    )
    mention_policy = fields.IntEnumField(
        MentionPolicy,
        description="How you want to handle mentions",
        default=MentionPolicy.ALLOW,
    )
    friend_policy = fields.IntEnumField(
        FriendPolicy,
        description="How you want to handle friend requests",
        default=FriendPolicy.ALLOW,
    )
    trade_cooldown_policy = fields.IntEnumField(
        TradeCooldownPolicy,
        description="How you want to handle trade accept cooldown",
        default=TradeCooldownPolicy.COOLDOWN,
    )
    extra_data = fields.JSONField(default=dict)
    balls: fields.BackwardFKRelation[BallInstance]

    def __str__(self) -> str:
        return str(self.discord_id)

    async def is_friend(self, other_player: "Player") -> bool:
        return await Friendship.filter(
            (Q(player1=self) & Q(player2=other_player))
            | (Q(player1=other_player) & Q(player2=self))
        ).exists()

    async def is_blocked(self, other_player: "Player") -> bool:
        return await Block.filter((Q(player1=self) & Q(player2=other_player))).exists()

    @property
    def can_be_mentioned(self) -> bool:
        return self.mention_policy == MentionPolicy.ALLOW


class BlacklistedID(models.Model):
    discord_id = fields.BigIntField(
        description="Discord user ID", unique=True, validators=[DiscordSnowflakeValidator()]
    )
    moderator_id = fields.BigIntField(
        description="Discord Moderator ID", validators=[DiscordSnowflakeValidator()], null=True
    )
    reason = fields.TextField(null=True, default=None)
    date = fields.DatetimeField(null=True, default=None, auto_now_add=True)

    def __str__(self) -> str:
        return str(self.discord_id)


class BlacklistedGuild(models.Model):
    discord_id = fields.BigIntField(
        description="Discord Guild ID", unique=True, validators=[DiscordSnowflakeValidator()]
    )
    moderator_id = fields.BigIntField(
        description="Discord Moderator ID", validators=[DiscordSnowflakeValidator()], null=True
    )
    reason = fields.TextField(null=True, default=None)
    date = fields.DatetimeField(null=True, default=None, auto_now_add=True)

    def __str__(self) -> str:
        return str(self.discord_id)


class BlacklistHistory(models.Model):
    id = fields.IntField(pk=True)
    discord_id = fields.BigIntField(
        description="Discord ID", validators=[DiscordSnowflakeValidator()]
    )
    moderator_id = fields.BigIntField(
        description="Discord Moderator ID", validators=[DiscordSnowflakeValidator()]
    )
    reason = fields.TextField(null=True, default=None)
    date = fields.DatetimeField(auto_now_add=True)
    id_type = fields.CharField(max_length=64, default="user")
    action_type = fields.CharField(max_length=64, default="blacklist")


class Trade(models.Model):
    id: int
    player1: fields.ForeignKeyRelation[Player] = fields.ForeignKeyField(
        "models.Player", related_name="trades"
    )
    player2: fields.ForeignKeyRelation[Player] = fields.ForeignKeyField(
        "models.Player", related_name="trades2"
    )
    date = fields.DatetimeField(auto_now_add=True)
    tradeobjects: fields.ReverseRelation[TradeObject]

    def __str__(self) -> str:
        return str(self.pk)

    class Meta:
        indexes = [
            PostgreSQLIndex(fields=("player1_id",)),
            PostgreSQLIndex(fields=("player2_id",)),
        ]


class TradeObject(models.Model):
    trade_id: int

    trade: fields.ForeignKeyRelation[Trade] = fields.ForeignKeyField(
        "models.Trade", related_name="tradeobjects"
    )
    ballinstance: fields.ForeignKeyRelation[BallInstance] = fields.ForeignKeyField(
        "models.BallInstance", related_name="tradeobjects"
    )
    player: fields.ForeignKeyRelation[Player] = fields.ForeignKeyField(
        "models.Player", related_name="tradeobjects"
    )

    def __str__(self) -> str:
        return str(self.pk)

    class Meta:
        indexes = [
            PostgreSQLIndex(fields=("ballinstance_id",)),
            PostgreSQLIndex(fields=("player_id",)),
            PostgreSQLIndex(fields=("trade_id",)),
        ]


class Friendship(models.Model):
    id: int
    player1: fields.ForeignKeyRelation[Player] = fields.ForeignKeyField(
        "models.Player", related_name="friend1"
    )
    player2: fields.ForeignKeyRelation[Player] = fields.ForeignKeyField(
        "models.Player", related_name="friend2"
    )
    since = fields.DatetimeField(auto_now_add=True)

    def __str__(self) -> str:
        return str(self.pk)


class Block(models.Model):
    id: int
    player1: fields.ForeignKeyRelation[Player] = fields.ForeignKeyField(
        "models.Player", related_name="block1"
    )
    player2: fields.ForeignKeyRelation[Player] = fields.ForeignKeyField(
        "models.Player", related_name="block2"
    )
    date = fields.DatetimeField(auto_now_add=True)

    def __str__(self) -> str:
        return str(self.pk)
