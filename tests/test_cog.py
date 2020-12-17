import random

from discord.ext import commands
from discord.ext.commands import group

from inhouse_bot.common_utils.emoji_and_thumbnails import get_champion_emoji
from inhouse_bot.database_orm import session_scope
from inhouse_bot.common_utils.validation_dialog import checkmark_validation
from inhouse_bot.common_utils.fields import roles_list, ChampionNameConverter
from inhouse_bot.common_utils.get_last_game import get_last_game
from inhouse_bot.game_queue import GameQueue
from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot import game_queue, matchmaking_logic
from inhouse_bot.queue_channel_handler import queue_channel_handler
from inhouse_bot.ranking_channel_handler.ranking_channel_handler import ranking_channel_handler


class TestCog(commands.Cog, name="TEST"):
    """
    This is a test cog meant for testing purposes

    As working with the Discord API makes it hard to write unit tests, this allows to do some integration tests
    """

    def __init__(self, bot: InhouseBot):
        self.bot = bot

    @group()
    async def test(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("This needs a subcommand")

    @test.command()
    async def validation(self, ctx: commands.Context):
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
        await queue_channel_handler.update_queue_channels(bot=self.bot, server_id=ctx.guild.id)

    @test.command()
    async def queue(self, ctx: commands.Context):
        """
        Testing the queue pop message
        """
        # We put 10 people in the queue
        for i in range(0, 10):
            game_queue.add_player(i, roles_list[i % 5], ctx.channel.id, ctx.guild.id, name=str(i))

        await ctx.send("The queue has been filled")
        await queue_channel_handler.update_queue_channels(bot=self.bot, server_id=ctx.guild.id)

    @test.command()
    async def duo(self, ctx: commands.Context):
        """
        Testing the duo queue feature
        """
        # We put 10 people in the queue
        for i in range(0, 10):
            game_queue.add_player(i, roles_list[i % 5], ctx.channel.id, ctx.guild.id, name=str(i))

        game_queue.add_duo(
            6,
            "JGL",
            ctx.author.id,
            "MID",
            ctx.channel.id,
            ctx.guild.id,
            first_player_name="6",
            second_player_name=ctx.author.display_name,
        )

        await ctx.send("The queue has been filled and you have been put in mid/jgl duo with player 6")

        await queue_channel_handler.update_queue_channels(bot=self.bot, server_id=ctx.guild.id)

    @test.command()
    async def game(self, ctx: commands.Context):
        """
        Creating a fake game in the database with players 0 to 8 and the ctx author
        """
        # We reset the queue
        # We put 9 people in the queue
        for i in range(0, 9):
            game_queue.add_player(i, roles_list[i % 5], ctx.channel.id, ctx.guild.id, name=str(i))

        game_queue.add_player(
            ctx.author.id, roles_list[4], ctx.channel.id, ctx.guild.id, name=ctx.author.display_name
        )

        game = matchmaking_logic.find_best_game(GameQueue(ctx.channel.id))

        with session_scope() as session:
            session.add(game)

        msg = await ctx.send("The queue has been reset, filled again, and a game created (with no winner)")

        game_queue.start_ready_check([i for i in range(0, 9)] + [ctx.author.id], ctx.channel.id, msg.id)
        game_queue.validate_ready_check(msg.id)
        await queue_channel_handler.update_queue_channels(bot=self.bot, server_id=ctx.guild.id)

    @test.command()
    async def games(self, ctx: commands.Context):
        """
        Creates 100 games in the database with random results
        """
        game_queue.reset_queue()

        for game_count in range(100):

            # We add the context creator as well
            game_queue.add_player(
                ctx.author.id, roles_list[4], ctx.channel.id, ctx.guild.id, name=ctx.author.display_name
            )

            # We put 15 people in the queue, but only the first ones should get picked
            for i in range(0, 15):
                game_queue.add_player(i, roles_list[i % 5], ctx.channel.id, ctx.guild.id, name=str(i))

            game = matchmaking_logic.find_best_game(GameQueue(ctx.channel.id))

            with session_scope() as session:
                session.add(game)
                winner = game.player_ids_list[int(random.random() * 10)]

            game_queue.start_ready_check([i for i in range(0, 9)] + [ctx.author.id], ctx.channel.id, 0)
            game_queue.validate_ready_check(0)

            matchmaking_logic.score_game_from_winning_player(player_id=winner, server_id=ctx.guild.id)

            await ranking_channel_handler.update_ranking_channels(self.bot, ctx.guild.id)

        await ctx.send("100 games have been created in the database")
        await queue_channel_handler.update_queue_channels(bot=self.bot, server_id=ctx.guild.id)

    @test.command()
    async def score(self, ctx: commands.Context):
        """
        Scores your last game as a win for (mostly made to be used after !test game)
        """
        matchmaking_logic.score_game_from_winning_player(player_id=ctx.author.id, server_id=ctx.guild.id)

        await ctx.send(f"{ctx.author.display_name}’s last game has been scored as a win")
        await queue_channel_handler.update_queue_channels(bot=self.bot, server_id=ctx.guild.id)

    @test.command()
    async def cancel(self, ctx: commands.Context):
        """
        Scores your last game as a win for (mostly made to be used after !test game)
        """
        with session_scope() as session:
            game, participant = get_last_game(
                player_id=ctx.author.id, server_id=ctx.guild.id, session=session
            )

            session.delete(game)

        await ctx.send(f"{ctx.author.display_name}’s last game was cancelled and deleted from the database")
        await queue_channel_handler.update_queue_channels(bot=self.bot, server_id=ctx.guild.id)

    @test.command()
    async def emoji(self, ctx: commands.Context, champion_id: ChampionNameConverter()):
        emoji_text = get_champion_emoji(champion_id, self.bot)

        await ctx.send(f"{champion_id} - {emoji_text}")

    # TODO LOW PRIO Write a test function to test accepting the queue/cancelling a game by spoofing reactions
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
