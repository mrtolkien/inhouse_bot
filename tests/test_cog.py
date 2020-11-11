import copy

from discord import Message, Reaction, User
from discord.ext import commands

from inhouse_bot.cogs.cogs_utils.validation_dialog import checkmark_validation
from inhouse_bot.common_utils import roles_list
from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot import game_queue


class TestCog(commands.Cog, name="TEST"):
    """
    This is a test cog meant for testing purposes

    As working with the Discord API makes it hard to write unit tests, this allows to do some integration tests
    """

    def __init__(self, bot: InhouseBot):
        self.bot = bot

    @commands.command()
    async def test_validation(self, ctx: commands.Context):
        """
        Testing the validation system

        You should try:
            Accepting with the checkmark
            Refusing with the cross
            Letting it timeout
        """
        message = await ctx.send("TEST REACTION MESSAGE WITH 5 SECONDS TIMEOUT")

        ready, players_to_drop = await checkmark_validation(
            bot=self.bot,
            message=message,
            validating_players_ids=[ctx.author.id],
            validation_threshold=1,
            timeout=5,
        )

        await ctx.send(f"{ready=}\n{players_to_drop=}")

    @commands.command()
    async def test_queue(self, ctx: commands.Context):
        """
        Testing the queue pop message
        """
        # We put 10 people in the queue
        for i in range(0, 10):
            game_queue.add_player(i, roles_list[i % 5], ctx.channel.id, ctx.guild.id, name=str(i))

        await ctx.send("The queue has been filled")

    # TODO A test function to test accepting the queue/cancelling a game
    # @commands.command()
    # async def test_accept_queue(self, ctx: commands.Context, queue_message_id):
    #     """
    #     Spoofing all 10 users accepting the queue
    #     """
    #     for i in range(0, 10):
    #         msg = copy.copy(ctx.message)
    #
    #         msg: Message
    #
    #         msg.id = queue_message_id
    #         msg.author = ctx.channel.guild.get_member(i)
    #         msg.reactions = [Reaction(message=msg, emoji=str("✅"), data={"count": 1, "me": i})]
    #
    #         new_ctx = await self.bot.get_context(msg, cls=type(ctx))
    #         new_ctx._db = ctx._db
    #
    #         await self.bot.invoke(new_ctx)
