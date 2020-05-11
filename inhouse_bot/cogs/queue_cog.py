import asyncio
import warnings
from collections import defaultdict
import itertools
import logging
import os

import discord
from discord import Embed
from discord.ext import commands
from rapidfuzz import process
from tabulate import tabulate

from inhouse_bot.cogs.cogs_utils import get_player
from inhouse_bot.common_utils import trueskill_blue_side_winrate
from inhouse_bot.sqlite.game import Game
from inhouse_bot.sqlite.game_participant import GameParticipant
from inhouse_bot.sqlite.player_rating import PlayerRating
from inhouse_bot.sqlite.sqlite_utils import roles_list


class QueueCog(commands.Cog, name='Queue'):
    def __init__(self, bot: commands.Bot):
        """
        :param bot: the bot to attach the cog to
        """
        self.bot = bot
        # [channel_id][role][list of Player objects]
        self.channel_queues = defaultdict(lambda: {role: set() for role in roles_list})

    @commands.command(help_index=0)
    async def queue(self, ctx: commands.Context, *, roles):
        """
        Puts you in a queue in the current channel for the specified roles.
        Roles are top, jungle, mid, bot, and support.

        Example usage:
            !queue support
            !queue mid bot
        """
        player = get_player(self.bot.session, ctx)

        # First, we check if the last game of the player is still ongoing.
        try:
            game, participant = player.get_last_game(self.bot.session)
            if not game.winner:
                await ctx.send('Your last game looks to be ongoing. '
                               'Please use !won or !lost to inform the result if the game is over.',
                               delete_after=10)
                return
        # This happens if the player has not played a game yet as get_last returns None and can’t be unpacked
        except TypeError:
            pass

        clean_roles = set()
        for role in roles.split(' '):
            clean_role, score = process.extractOne(role, roles_list)
            if score < 80:
                continue
            else:
                clean_roles.add(clean_role)

        if not clean_roles:
            await ctx.send('Role name was not properly understood. '
                           'Working values are top, jungle, mid, bot, and support.',
                           delete_after=10)
            return

        for role in clean_roles:
            self.add_player_to_queue(player, role, ctx.channel.id)

        for role in clean_roles:
            # Dirty code to get the emoji related to the letters
            await ctx.message.add_reaction(chr(127462 + (ord(f"{role[0]}") - 97)))

        await self.matchmaking_process(ctx)

    @commands.command(help_index=1, aliases=['leave'])
    async def leave_queue(self, ctx: commands.Context, *args):
        """
        Removes you from the queue in the current channel or all channels with !stop_queue all.

        Example usage:
            !stop_queue
            !stop_queue all
        """
        player = get_player(self.bot.session, ctx)

        await self.remove_player_from_queue(player, ctx.channel.id if not args else None, ctx)

    @commands.command(help_index=2, aliases=['win'])
    async def won(self, ctx: commands.context):
        """
        Scores your last game as a win.
        """
        await self.score_game(ctx, True)

    @commands.command(help_index=3, aliases=['loss', 'defeat', 'ff', 'lose'])
    async def lost(self, ctx: commands.context):
        """
        Scores your last game as a loss.
        """
        await self.score_game(ctx, False)

    @commands.command(help_index=4)
    async def champion(self, ctx, champion_name, game_id=None):
        """
        Informs the champion you used for the chosen game (or the last game by default)

        Example:
            !champion riven
            !champion riven 1
        """
        champion_id, ratio = self.bot.lit.get_id(champion_name, input_type='champion', return_ratio=True)

        if ratio < 75:
            await ctx.send('Champion name was not understood properly.\nUse `!help won` for more information.',
                           delete_after=30)
            return

        player = get_player(self.bot.session, ctx)
        if game_id:
            game, participant = self.bot.session.query(Game, GameParticipant).join(GameParticipant) \
                .filter(Game.id == game_id) \
                .filter(GameParticipant.player_id == player.discord_id) \
                .order_by(Game.date.desc()) \
                .first()
        else:
            game, participant = player.get_last_game(self.bot.session)

        participant.champion_id = champion_id
        self.bot.session.merge(participant)

        self.bot.session.commit()

        log_message = f'Champion for game {game.id} set to {self.bot.lit.get_name(participant.champion_id)} for {player.name}'

        logging.info(log_message)
        await ctx.send(log_message, delete_after=10)

    @commands.command(help_index=5)
    async def view_queue(self, ctx: commands.Context):
        """
        Shows the active queue in the channel.
        """
        table = [[]]
        for role in roles_list:
            table.append([role.capitalize()] + sorted([p.name for p in self.channel_queues[ctx.channel.id][role]]))

        embed = Embed(title='Current queue', colour=discord.colour.Colour.dark_red())
        embed.add_field(name='Queue', value=f'```{tabulate(table, tablefmt="plain")}```')

        await ctx.send(embed=embed)

    @commands.command(help_index=6)
    async def view_games(self, ctx: commands.context):
        """
        Shows the ongoing inhouse games.
        """
        games_without_results = self.bot.session.query(Game).filter(Game.winner == None).all()

        if not games_without_results:
            await ctx.send('No active games found', delete_after=10)
            return

        embed = Embed(title='Ongoing games', colour=discord.colour.Colour.dark_blue())
        for game in games_without_results:
            embed.add_field(name=f'Game {game.id}',
                            value=f'```{game}```')

        await ctx.send(embed=embed)

    @commands.command(help_index=7, aliases=['cancel'])
    async def cancel_game(self, ctx: commands.context):
        """
        Cancels and voids your ongoing game. Require validation from other players in the game.
        """
        player = get_player(self.bot.session, ctx)

        game, participant = player.get_last_game(self.bot.session)

        # If the game is already done and scored, we don’t offer cancellation anymore.
        if game.winner:
            no_cancel_notice = f'You don’t seem to currently be in a game.'
            logging.info(no_cancel_notice)
            await ctx.send(no_cancel_notice)
            return

        cancelling_game_message = await ctx.send('Trying to cancel the game including {}.\n'
                                                 'If you want to cancel the game, have at least 6 players press ✅.\n'
                                                 'If you did not mean to cancel the game, press ❎.'
                                                 .format(
            ', '.join(['<@{}>'.format(p.player) for p in game.participants])),
                                                 delete_after=60)

        if not await self.checkmark_validation(cancelling_game_message,
                                               [p.player.discord_id for p in game.participants],
                                               6):
            # If there’s no validation, we just inform players nothing happened and leave
            no_cancellation_message = f'Cancellation canceled.'
            logging.info(no_cancellation_message)
            await ctx.send(no_cancellation_message, delete_after=30)
            return

        # If we get here, 6+ players accepted to cancel the game
        self.bot.session.delete(game)
        self.bot.session.commit()

        cancel_notice = f'Game {game.id} cancelled.'

        logging.info(cancel_notice)
        await ctx.send(cancel_notice)

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def admin_score(self, ctx, game_id, winning_team):
        """
        Admin-only way to score an active match. Needs game_id and winner (blue/red)

        Example:
            !admin_score 1 blue
            !admin_score 3 red
        """
        game = self.bot.session.query(Game).filter(Game.id == game_id).one()

        if game.winner:
            await ctx.send('It is currently impossible the change the result of a game that was scored because it would '
                           'create huge issues with rating recalculations.')
            return

        if winning_team not in ['blue', 'red']:
            await ctx.send('The winning team must be blue or red.\n'
                           'Example: `!admin_score 1 blue`')
            return

        game.winner = winning_team

        self.bot.session.commit()
        game.update_trueskill(self.bot.session)

        message = f'Game {game.id} has been scored as a win for {game.winner} and ratings have been updated.'

        logging.info(message)
        await ctx.send(message)

    def add_player_to_queue(self, player, role, channel_id):
        if role not in player.ratings:
            logging.info('Creating a new PlayerRating for <{}> <{}>'.format(player.discord_string, role))
            new_rating = PlayerRating(player, role)
            self.bot.session.add(new_rating)
            self.bot.session.commit()
            # This step is required so our player object has access to the rating
            player = self.bot.session.merge(player)

        # Actually adding the player to the queue
        self.channel_queues[channel_id][role].add(player)
        logging.info(f'Player <{player.discord_string}> has been added to the <{role}><{channel_id}> queue')

    async def remove_player_from_queue(self, player, channel_id=None, ctx=None):
        """
        Removes the given player from queue.

        If given a channel_id, only removes the player from the given channel.
        If given a context message, thumbs ups it.
        """
        for channel_id in self.channel_queues if not channel_id else [channel_id]:
            for role in self.channel_queues[channel_id]:
                self.channel_queues[channel_id][role].discard(player)

        logging.info('Player <{}> has been removed from {}'
                     .format(player.discord_string,
                             'all queues' if not channel_id else 'the <{}> queue'.format(channel_id)))

        if ctx:
            await ctx.message.add_reaction('👍')

    async def matchmaking_process(self, ctx):
        """
        Start the matchmaking process in the given channel.

        This function is split in multiple functions for easier testing.
        """
        # Match quality returns -1 when matchmaking can’t be done
        players, match_quality = self.find_best_game(ctx.channel.id)

        # We have a good match
        if match_quality > -0.1:
            await self.start_game(ctx, players)
        # We have a match that could be slightly one-sided
        elif match_quality > -0.2:
            await self.start_game(ctx, players, mismatch=True)

    def find_best_game(self, channel_id) -> tuple:
        """
        Looks at the queue in the channel and returns the best match-made game (as a {team, role] -> Player}.
        """
        # Do not do anything if there’s not at least 2 players in queue per role
        for role in roles_list:
            if self.channel_queues[channel_id][role].__len__() < 2:
                logging.debug('Not enough players to start matchmaking')
                return None, -1

        logging.info('Starting matchmaking process')

        # Simply testing all permutations because it should be pretty lightweight
        # TODO Spot mirrored team compositions (full blue/red -> red/blue) to not calculate them twice
        role_permutations = []
        for role in roles_list:
            role_permutations.append([p for p in itertools.permutations(self.channel_queues[channel_id][role], 2)])

        # Very simple maximum search
        best_score = -1
        best_players = {}
        for team_composition in itertools.product(*role_permutations):
            # players: [team, role] -> Player
            players = {('red' if tuple_idx else 'blue', roles_list[role_idx]): players_tuple[tuple_idx]
                       for role_idx, players_tuple in enumerate(team_composition)
                       for tuple_idx in (0, 1)}
            # We check to make sure all 10 players are different
            if set(players.values()).__len__() != 10:
                continue

            # Defining the score as -|0.5-expected_blue_winrate| to be side-agnostic.
            score = -abs(0.5 - trueskill_blue_side_winrate(players))

            if score > best_score:
                best_players = players
                best_score = score
                # If the game is seen as being below 51% winrate for one side, we simply stop there
                if best_score > -0.01:
                    break

        logging.info('The best match found had a score of {}'.format(best_score))

        return best_players, best_score

    async def start_game(self, ctx, players, mismatch=False):
        """
        Attempts to start the given game by pinging players and waiting for their reactions.
        """
        # Start by removing all players from the channel queue before starting the game
        for player in players.values():
            await self.remove_player_from_queue(player, channel_id=ctx.channel.id)

        game = Game(players)
        self.bot.session.add(game)
        self.bot.session.commit()

        if not await self.ready_check(ctx, players, mismatch, game):
            # If the ready check fails, we delete the game and let !queue handle restarting matchmaking.
            self.bot.session.delete(game)
            self.bot.session.commit()
            await ctx.send('The game has been cancelled. You can queue again.')
            return

        logging.info(f'Starting game {game.id}')
        await ctx.send(f'Game {game.id} has started!')

    async def ready_check(self, ctx: commands.Context, players, mismatch, game):
        """
        Posts a message in the given context, pinging the 10 players, trying to start the game.

        If all 10 players accept the game, returns True.
        If not, returns False.
        """
        # TODO Find a clean way to handle this test with a mock instead (and remove that snippet)
        if 'PYTEST_CURRENT_TEST' in os.environ:
            return True

        logging.info('Starting a game ready check.')

        embed = Embed(title='Proposed game')
        embed.add_field(name='Team compositions',
                        value=f'```{game}```')

        if mismatch:
            embed.add_field(name='WARNING',
                            value='According to TrueSkill, this game might be a slight mismatch.')

        ready_check_message = await ctx.send('A match has been found for {}.\n'
                                             'All players have been dropped from queues they were in.\n'
                                             'You can refuse the match and leave the queue by pressing ❎.\n'
                                             'If you are ready, press ✅.'
            .format(
            ', '.join(['<@{}>'.format(p.discord_id) for p in players.values()])), embed=embed)

        return await self.checkmark_validation(ready_check_message, [p.discord_id for p in players.values()], 10)

    async def score_game(self, ctx, result: bool):
        """
        Scores the player’s last game with the given result.
        """
        player = get_player(self.bot.session, ctx)

        game, game_participant = player.get_last_game(self.bot.session)

        if game.winner:
            # Conflict between entered results and current results
            await ctx.send(f'**Your last game’s result was already entered and validated**', delete_after=30)
            return

        game.winner = 'blue' if game_participant.team == 'blue' and result else 'red'

        ready_check_message = await ctx.send(f'{player.name} wants to score game {game.id} as a win for {game.winner}\n'
                                             f'{", ".join(["<@{}>".format(p.player_id) for p in game.participants.values()])}\n'
                                             f'Result will be validated once 6 players from the game press ✅.',
                                             delete_after=120)

        if not await self.checkmark_validation(ready_check_message, [p.player_id for p in game.participants.values()], 6):
            await ctx.send('Game result input cancelled.', delete_after=60)
            return

        self.bot.session.commit()
        game.update_trueskill(self.bot.session)

        message = f'Game {game.id} has been scored as a win for {game.winner} and ratings have been updated.'

        logging.info(message)
        await ctx.send(message)

    async def checkmark_validation(self, message: discord.Message,
                                   validating_members: [],
                                   validation_threshold: int,
                                   timeout=120.0):
        """
        Implements a checkmark validation on the chosen message.

        Returns True if validation_threshold members in validating_members pressed '✅' before the timeout.
        """
        await message.add_reaction('✅')
        await message.add_reaction('❎')

        def check(received_reaction: discord.Reaction, sending_user: discord.User):
            # This check is simply used to see if a player in the game responded to the message.
            # Queue logic is handled below
            return received_reaction.message.id == message.id and \
                   sending_user.id in validating_members and \
                   str(received_reaction.emoji) in ['✅', '❎']

        members_who_validated = set()
        try:
            while True:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=timeout, check=check)

                if str(reaction.emoji) == '✅':
                    members_who_validated.add(user.id)
                    if members_who_validated.__len__() >= validation_threshold:
                        return True

                elif str(reaction.emoji) == '❎':
                    return False

        # We get there if no player accepted in the last two minutes
        except asyncio.TimeoutError:
            return False
