import random

from discord.ext import commands
from discord.ext.commands import group

from inhouse_bot.config.emoji_and_thumbnaills import get_champion_emoji
from inhouse_bot.orm import session_scope
from inhouse_bot.cogs.cogs_utils.validation_dialog import checkmark_validation
from inhouse_bot.common_utils.fields import roles_list, ChampionNameConverter
from inhouse_bot.common_utils.get_last_game import get_last_game
from inhouse_bot.game_queue import GameQueue
from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot import game_queue, matchmaking_logic


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

    @test.command()
    async def queue(self, ctx: commands.Context):
        """
        Testing the queue pop message
        """
        # We put 10 people in the queue
        for i in range(0, 10):
            game_queue.add_player(i, roles_list[i % 5], ctx.channel.id, ctx.guild.id, name=str(i))

        await ctx.send("The queue has been filled")

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

    @test.command()
    async def games(self, ctx: commands.Context):
        """
        Creates 100 games in the database with random results
        """
        game_queue.reset_queue()

        for game_count in range(100):

            # We reset the queue
            # We put 20 people in the queue
            for i in range(0, 20):
                game_queue.add_player(i, roles_list[i % 5], ctx.channel.id, ctx.guild.id, name=str(i))

            # We add the context creator as well
            game_queue.add_player(
                ctx.author.id, roles_list[4], ctx.channel.id, ctx.guild.id, name=ctx.author.display_name
            )

            game = matchmaking_logic.find_best_game(GameQueue(ctx.channel.id))

            with session_scope() as session:
                session.add(game)

            game_queue.start_ready_check([i for i in range(0, 9)] + [ctx.author.id], ctx.channel.id, 0)
            game_queue.validate_ready_check(0)

            matchmaking_logic.score_game_from_winning_player(
                player_id=int(random.random() * 9), server_id=ctx.guild.id
            )

        await ctx.send("100 games have been created in the database")

    @test.command()
    async def score(self, ctx: commands.Context):
        """
        Scores your last game as a win for (mostly made to be used after !test game)
        """
        matchmaking_logic.score_game_from_winning_player(player_id=ctx.author.id, server_id=ctx.guild.id)

        await ctx.send(f"{ctx.author.display_name}’s last game has been scored as a win")

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

    @test.command()
    async def emoji(self, ctx: commands.Context, champion_id: ChampionNameConverter()):
        emoji_text = get_champion_emoji(champion_id, self.bot)

        await ctx.send(f"{champion_id} - {emoji_text}")

    # TODO LOW PRIO A test function to test accepting the queue/cancelling a game by spoofing reactions
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
