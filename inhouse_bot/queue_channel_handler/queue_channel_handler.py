import asyncio
import logging
from typing import List, Optional

from discord import Message, Embed, TextChannel
from discord.ext import commands
from discord.ext.commands import Bot

from inhouse_bot import game_queue
from inhouse_bot.common_utils.constants import PREFIX
from inhouse_bot.common_utils.embeds import embeds_color
from inhouse_bot.common_utils.emoji_and_thumbnails import get_role_emoji
from inhouse_bot.database_orm import session_scope, ChannelInformation

queue_logger = logging.getLogger("queue_channel_handler")


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

        # channel_id -> GameQueue
        self._queue_cache = {}

        # Helps untag older message that needs to be deleted
        self.latest_queue_message_ids = {}

        # IDs of messages we do not want to delete directly
        self.permanent_messages = set()

        # Guarantees we do not purge too fast
        self.latest_purge_message_id = {}

    async def queue_channel_message_listener(self, msg: Message):
        """
        This is a listener that’s meant to be called on all messages and delete unnecessary ones in the queue channels
        """

        # We check if the message is in a queue channel
        if self.is_queue_channel(msg.channel.id):

            # If it was, we trigger a purge of non-marked messages

            # We save the msg id and will only delete if it’s still the latest msg in the channel to purge after 5s
            self.latest_purge_message_id[msg.channel.id] = msg.id

            await asyncio.sleep(5)  # Hardcoded right now, will need a sanity pass

            if self.latest_purge_message_id[msg.channel.id] == msg.id:
                await msg.channel.purge(check=self.is_not_queue_related_message)

    async def refresh_channel_queue(self, channel: TextChannel, restart: bool):
        """
        Deletes the previous queue message and sends a new one in the channel

        If channel is supplied instead of a context (in the case of a bot reboot), send the reboot message instead
        """

        # Creating the queue visualisation requires getting the Player objects from the DB to have the names
        queue = game_queue.GameQueue(channel.id)

        # If the new queue is the same as the cache, we simple return
        if queue == self._queue_cache.get(channel.id):
            return
        else:
            # Else, we update our cache (useful to not send too many messages)
            self._queue_cache[channel.id] = queue

        # Create the queue embed
        embed = Embed(colour=embeds_color)

        # Adding queue field
        queue_rows = []

        for role, role_queue in queue.queue_players_dict.items():
            queue_rows.append(
                f"{get_role_emoji(role)} " + ", ".join(qp.player.short_name for qp in role_queue)
            )

        embed.add_field(name="Queue", value="\n".join(queue_rows))

        # Adding duos field if it’s not empty
        if queue.duos:
            duos_strings = []

            for duo in queue.duos:

                duos_strings.append(
                    " + ".join(f"{qp.player.short_name} {get_role_emoji(qp.role)}" for qp in duo)
                )

            embed.add_field(name="Duos", value=", ".join(duos_strings))

        embed.set_footer(
            text=f"Use {PREFIX}queue [role] to join or !leave to leave | All non-queue messages are deleted"
        )

        message_text = ""

        if restart:
            message_text += (
                "\nThe bot was restarted and all players in ready-check have been put back in queue\n"
                "The matchmaking process will restart once anybody queues or re-queues"
            )

        # We save the message object in our local cache
        new_queue_message = await channel.send(message_text, embed=embed,)

        self.latest_queue_message_ids[channel.id] = new_queue_message.id

    @property
    def queue_channel_ids(self) -> List[int]:
        return [c.id for c in self._queue_channels]

    def get_server_queues(self, server_id: int) -> List[int]:
        return [c.id for c in self._queue_channels if c.server_id == server_id]

    def is_queue_channel(self, channel_id) -> bool:
        return channel_id in self.queue_channel_ids

    def is_not_queue_related_message(self, msg) -> bool:
        return (msg.id not in self.permanent_messages) and (
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

        queue_logger.info(f"Marked {channel_id} as a queue channel")

    def unmark_queue_channel(self, channel_id):
        game_queue.reset_queue(channel_id)

        with session_scope() as session:
            channel_query = session.query(ChannelInformation).filter(ChannelInformation.id == channel_id)
            channel_query.delete(synchronize_session=False)

        self._queue_channels = [c for c in self._queue_channels if c.id != channel_id]

        queue_logger.info(f"Unmarked {channel_id} as a queue channel")

    def mark_queue_related_message(self, msg):
        self.permanent_messages.add(msg.id)

    # Needs unmark to make sure the object does not get too full
    def unmark_queue_related_message(self, msg):
        self.permanent_messages.remove(msg.id)

    async def update_queue_channels(self, bot: Bot, server_id: Optional[int]):
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

        for channel_id in channels_to_check:
            channel = bot.get_channel(channel_id)

            if not channel:  # Happens when the channel does not exist anymore
                self.unmark_queue_channel(channel_id)  # We remove it for the future
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
