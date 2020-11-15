from typing import List

from discord.ext import commands

from inhouse_bot.orm import session_scope, ChannelInformation


# TODO This should have a mark_queue_channel function and a cache common to all functions

def mark_queue_channel(channel_id, server_id):
    """
    Marks the given channel + server combo as a queue
    """
    channel = ChannelInformation(
        id=channel_id, server_id=server_id, channel_type="QUEUE"
    )
    with session_scope() as session:
        session.merge(channel)


def get_queue_channels() -> List[int]:
    # Very stupid way to do it, need opti
    # TODO MED PRO Cache it except on admin addition (make a common module to handle it)
    with session_scope() as session:
        session.expire_on_commit = False
        channels = (
            session.query(ChannelInformation.id).filter(ChannelInformation.channel_type == "QUEUE").all()
        )

    return [c.id for c in channels]


class QueueChannelsOnlyError(commands.CheckFailure):
    pass


# This is meant to be a decorator for classes
def queue_channel_only():
    async def predicate(ctx):
        if ctx.channel.id not in get_queue_channels():
            raise QueueChannelsOnlyError
        else:
            return True

    return commands.check(predicate)
