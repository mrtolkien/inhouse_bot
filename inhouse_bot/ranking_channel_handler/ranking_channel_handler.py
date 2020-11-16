from typing import Optional, List

import sqlalchemy
from discord import TextChannel, Message, Embed
from discord.ext import commands
from discord.ext.commands import Bot
from sqlalchemy import func

from inhouse_bot.database_orm import (
    ChannelInformation,
    session_scope,
    Player,
    PlayerRating,
    Game,
    GameParticipant,
)
from inhouse_bot.stats_menus.ranking_pages import RankingPagesSource


class RankingChannelHandler:
    # TODO post ranking, purge channel, update after game has been scored
    def __init__(self):
        # TODO LOW PRIO make sure there is only 1 ranking queue per server?
        with session_scope() as session:
            session.expire_on_commit = False

            self._ranking_channels = (
                session.query(ChannelInformation.id, ChannelInformation.server_id)
                .filter(ChannelInformation.channel_type == "RANKING")
                .all()
            )

        # channel id -> message
        self.ranking_messages = {}

    @property
    def ranking_channel_ids(self) -> List[int]:
        return [c.id for c in self._ranking_channels]

    def get_server_ranking_channels(self, server_id: int) -> List[int]:
        return [c.id for c in self._ranking_channels if c.server_id == server_id]

    def mark_ranking_channel(self, channel_id, server_id):
        """
        Marks the given channel + server combo as a queue
        """
        channel = ChannelInformation(id=channel_id, server_id=server_id, channel_type="RANKING")
        with session_scope() as session:
            session.merge(channel)

        self._ranking_channels.append(channel)

    def unmark_ranking_channel(self, channel_id):

        with session_scope() as session:
            channel_query = session.query(ChannelInformation).filter(ChannelInformation.id == channel_id)
            channel_query.delete(synchronize_session=False)

        self._ranking_channels = [c for c in self._ranking_channels if c.id != channel_id]

    async def update_ranking_channels(self, bot: Bot, server_id: Optional[int]):
        if not server_id:
            channels_to_update = self.ranking_channel_ids
        else:
            channels_to_update = self.get_server_ranking_channels(server_id)

        for channel_id in channels_to_update:
            channel = bot.get_channel(channel_id)

            if not channel:  # Happens when the channel does not exist anymore
                self.unmark_ranking_channel(channel_id)  # We remove it for the future
                continue

            await self.refresh_channel_rankings(channel=channel, bot=bot)

    async def refresh_channel_rankings(self, channel: TextChannel, bot: Bot):
        ranking_message = self.ranking_messages.get(channel.id)
        ranking_message: Message

        if not ranking_message:
            # We create a ranking message and restart
            self.ranking_messages[channel.id] = await channel.send(embed=Embed(description="Loading ranking..."))
            await self.refresh_channel_rankings(channel, bot)
            return

        ratings = self.get_server_ratings(channel.guild.id, limit=30)
        source = RankingPagesSource(ratings, bot, embed_name_suffix=f"on {channel.guild.name}")

        await ranking_message.edit(embed=await source.format_page(menu=None, entries=ratings))

        # Finally, we do that just in case
        await channel.purge(check=lambda msg: msg.id != ranking_message.id)

    @staticmethod
    def get_server_ratings(server_id: int, role: str = None, limit=100):
        with session_scope() as session:
            session.expire_on_commit = False

            ratings = (
                session.query(
                    Player,
                    PlayerRating.player_server_id,
                    PlayerRating.mmr,
                    PlayerRating.role,
                    func.count().label("count"),
                    (
                        sqlalchemy.func.sum((Game.winner == GameParticipant.side).cast(sqlalchemy.Integer))
                    ).label(
                        "wins"
                    ),  # A bit verbose for sure
                )
                .select_from(Player)
                .join(PlayerRating)
                .join(GameParticipant)
                .join(Game)
                .filter(Player.server_id == server_id)
                .group_by(Player, PlayerRating)
                .order_by(PlayerRating.mmr.desc())
            )

            if role:
                ratings = ratings.filter(PlayerRating.role == role)

            ratings = ratings.limit(limit).all()

        return ratings


ranking_channel_handler = RankingChannelHandler()
