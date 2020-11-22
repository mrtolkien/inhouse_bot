from typing import Optional, List

import sqlalchemy
from discord import TextChannel
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
    def __init__(self):
        with session_scope() as session:
            session.expire_on_commit = False

            self._ranking_channels = (
                session.query(ChannelInformation.id, ChannelInformation.server_id)
                .filter(ChannelInformation.channel_type == "RANKING")
                .all()
            )

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

            await self.refresh_channel_rankings(channel=channel)

    async def refresh_channel_rankings(self, channel: TextChannel):
        ratings = self.get_server_ratings(channel.guild.id, limit=30)

        # We need 3 messages because of character limits
        source = RankingPagesSource(ratings, embed_name_suffix=f"on {channel.guild.name}")

        new_msgs_ids = set()
        for page in range(0, 3):
            if page < source.get_max_pages():
                rating_message = await channel.send(
                    embed=await source.format_page(None, await source.get_page(page), offset=page)
                )
                new_msgs_ids.add(rating_message.id)

        # Finally, we do that just in case
        await channel.purge(check=lambda msg: msg.id not in new_msgs_ids)

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
                .filter(Game.winner != None)    # No currently running game
                .group_by(Player, PlayerRating)
                .order_by(PlayerRating.mmr.desc())
            )

            if role:
                ratings = ratings.filter(PlayerRating.role == role)

            ratings = ratings.limit(limit).all()

        return ratings


ranking_channel_handler = RankingChannelHandler()
