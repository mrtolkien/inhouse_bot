import asyncio
from typing import List, Optional

from discord import Message, Embed, TextChannel
from discord.ext import commands
from discord.ext.commands import Bot

from inhouse_bot import game_queue
from inhouse_bot.config.embeds import embeds_color
from inhouse_bot.config.emoji_and_thumbnaills import get_role_emoji
from inhouse_bot.game_queue import reset_queue
from inhouse_bot.orm import session_scope, ChannelInformation


class QueueChannelHandler:
    def __init__(self):
        # We reload the queue channels from the database on restart
        with session_scope() as session:
            session.expire_on_commit = False

            self._queue_channels = (
                session.query(ChannelInformation.id, ChannelInformation.server_id)
                .filter(ChannelInformation.channel_type == "QUEUE")
                .all()
            )

        # channel_id -> GameQueue, to know when there were updates?
        self._queue_cache = {}

        # Helps untag older message that needs to be deleted
        self.latest_queue_message_ids = {}

        # IDs of messages we do not want to delete
        self.queue_related_messages_ids = set()

    async def purge_queue_channels(self, msg: Message):
        # We check if the message is in a queue channel
        if self.is_queue_channel(msg.channel.id):
            # If it was, we trigger a purge of non-marked messages

            await asyncio.sleep(5)  # Hardcoded right now, will need a sanity pass
            await msg.channel.purge(check=self.is_not_queue_related_message)

    async def refresh_channel_queue(self, channel: TextChannel, restart: bool):
        """
        Deletes the previous queue message and sends a new one in the channel

        If channel is supplied instead of a context (in the case of a bot reboot), send the reboot message instead
        """

        rows = []

        # Creating the queue visualisation requires getting the Player objects from the DB to have the names
        queue = game_queue.GameQueue(channel.id)

        for role, role_queue in queue.queue_players_dict.items():
            rows.append(f"{get_role_emoji(role)} " + ", ".join(qp.player.short_name for qp in role_queue))

        # Create the queue embed
        embed = Embed(colour=embeds_color)
        embed.add_field(name="Queue", value="\n".join(rows))
        embed.set_footer(
            text="Use !queue [role] to queue | All non-queue messages in this channel are deleted"
        )

        # We save the message object in our local cache
        new_queue = await channel.send(
            "The bot was restarted and all players in ready-check have been put back in queue\n"
            "The matchmaking process will restart once anybody queues or re-queues"
            if channel
            else None,
            embed=embed,
        )

        self.latest_queue_message_ids[channel.id] = new_queue.id

    @property
    def queue_channel_ids(self) -> List[int]:
        return [c.id for c in self._queue_channels]

    def get_server_queues(self, server_id: int) -> List[int]:
        return [c.id for c in self._queue_channels if c.server_id == server_id]

    def is_queue_channel(self, channel_id) -> bool:
        return channel_id in self.queue_channel_ids

    def is_not_queue_related_message(self, msg) -> bool:
        return (msg.id not in self.queue_related_messages_ids) and (
            msg.id not in self.latest_queue_message_ids.values()
        )

    def mark_queue_channel(self, channel_id, server_id):
        """
        Marks the given channel + server combo as a queue
        """
        channel = ChannelInformation(id=channel_id, server_id=server_id, channel_type="QUEUE")
        with session_scope() as session:
            session.merge(channel)

        self._queue_channels.append(channel)

    def remove_queue_channel(self, channel_id):
        game_queue.reset_queue(channel_id)

        with session_scope() as session:
            reset_queue(channel_id)

            channel_query = session.query(ChannelInformation).filter(ChannelInformation.id == channel_id)

            channel_query.delete(synchronize_session=False)

        self._queue_channels = [c for c in self._queue_channels if c.id != channel_id]

    def mark_queue_related_message(self, msg):
        self.queue_related_messages_ids.add(msg.id)

    def unmark_queue_related_message(self, msg):
        self.queue_related_messages_ids.remove(msg.id)

    async def update_server_queues(self, bot: Bot, server_id: Optional[int]):
        """
        Updates the queues in the given server

        If the server is not specified (restart), updates queue in all tagged queue channels
        """
        if not server_id:
            restart = True
            channels_to_check = self.queue_channel_ids
        else:
            restart = False
            channels_to_check = self.get_server_queues(server_id)

        # TODO This is just restart code atm, should handle all cases with queue caching

        for channel_id in channels_to_check:
            channel = bot.get_channel(channel_id)

            if not channel:  # Happens when the channel does not exist anymore
                self.remove_queue_channel(channel_id)  # We remove it for the future
                continue

            await self.refresh_channel_queue(channel=channel, restart=restart)


# This will be an object common to all functions afterwards
queue_channel_handler = QueueChannelHandler()


class QueueChannelsOnly(commands.CheckFailure):
    pass


# This is a decorator for commands
def queue_channel_only():
    async def predicate(ctx):
        if ctx.channel.id not in queue_channel_handler.queue_channel_ids:
            raise QueueChannelsOnly
        else:
            return True

    return commands.check(predicate)
