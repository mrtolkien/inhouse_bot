from discord import Embed
from discord.ext import commands
from discord.ext.commands import guild_only

from inhouse_bot.bot_orm import session_scope

from inhouse_bot.common_utils import roles_list, RoleConverter
from inhouse_bot.common_utils.is_in_game import get_last_game
from inhouse_bot.config.embeds import embeds_color
from inhouse_bot.config.emoji import get_role_emoji

from inhouse_bot import game_queue
from inhouse_bot import matchmaking_logic

from inhouse_bot.inhouse_bot import InhouseBot


class QueueCog(commands.Cog, name="Queue"):
    def __init__(self, bot: InhouseBot):
        self.bot = bot

        self.latest_queue_messages = {}

    async def send_queue(self, ctx: commands.Context, queue: game_queue.GameQueue):
        """
        Deletes the previous queue message and sends a new one in the channel
        """
        try:
            old_queue_message = self.latest_queue_messages[ctx.channel.id]
        except KeyError:
            old_queue_message = None

        rows = []

        # Creating the queue visualisation requires getting the Player objects from the DB to have the names
        with session_scope() as session:
            queue_players = game_queue.get_queue_players(queue, session)

            # We need to check all roles to still look good even with empty queues
            for role in roles_list:
                rows.append(f"{get_role_emoji(role)} " + ", ".join(p.name for p in queue_players[role]))

        # Create the queue embed
        embed = Embed(colour=embeds_color)
        embed.add_field(name="Queue", value="\n".join(rows))

        # We save the message object in our local cache
        self.latest_queue_messages[ctx.channel.id] = await ctx.send(embed=embed)

        # Sequenced that way for smoother scrolling in discord
        if old_queue_message:
            await old_queue_message.delete()

    @commands.command()
    @guild_only()
    async def queue(
        self, ctx: commands.Context, role: RoleConverter(),
    ):
        """
        Puts you in a queue in the current channel for the specified roles.
        Roles are TOP, JGL, MID, BOT/ADC, and SUP

        Example usage:
            !queue SUP
            !queue support
            !queue bot
            !queue adc
        """

        # Actually queuing the player
        queue = game_queue.add_player(
            player_id=ctx.author.id,
            name=ctx.author.name,
            role=role,
            channel_id=ctx.channel.id,
            server_id=ctx.guild.id,
        )

        if game := matchmaking_logic.find_best_game(queue):
            score = abs(0.5 - game.blue_expected_winrate)

            if score < 0.1:
                # Good situation where we have a relatively fair game
                ...
            if score < 0.2:
                # Acceptable situation where we will still start the game
                ...
            else:
                # One side has over 70% predicted winrate, we do not start
                await ctx.send(
                    f"The best match found had a side with a {.5 + score} predicted winrate and therefore did not start"
                )

        # Currently, we only update the current queue even if other queues got changed
        await self.send_queue(ctx=ctx, queue=queue)

    @commands.command(aliases=["leave", "stop"])
    @guild_only()
    async def leave_queue(
        self, ctx: commands.Context,
    ):
        """
        Removes you from the queue in the current channel

        Example usage:
            !stop_queue
        """

        queue = game_queue.remove_player(player_id=ctx.author.id, channel_id=ctx.channel.id)

        # Currently, we only update the current queue even if other queues got changed
        await self.send_queue(ctx=ctx, queue=queue)

    @commands.command(aliases=["win", "wins", "victory"])
    @guild_only()
    async def won(
        self, ctx: commands.Context,
    ):
        """
        Scores your last game as a win
        """
        with session_scope() as session:
            # Get the latest game
            game, participant = get_last_game(
                player_id=ctx.author.id, server_id=ctx.guild.id, session=session
            )

            if game and game.winner:
                await ctx.send("Your last game seem to have already been scored")
                return

            # TODO Display the game with the winner and tag the players to vote

        matchmaking_logic.score_game_from_winning_player(player_id=ctx.author.id, server_id=ctx.guild.id)

    @commands.command(aliases=["cancel"])
    @guild_only()
    async def cancel_game(
        self, ctx: commands.Context,
    ):
        """
        Cancels your last game after it has been accepted but before it was scored
        """
        with session_scope() as session:
            # Get the latest game
            game, participant = get_last_game(
                player_id=ctx.author.id, server_id=ctx.guild.id, session=session
            )

            if game and game.winner:
                await ctx.send("It does not look like you are part of an ongoing game")
                return

            # TODO Display the game and tag the players to vote and cancel the game (*ie* delete it from DB)

    # TODO Add admins functions (!reset, !cancel, !score)
