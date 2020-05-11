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


class QueueCog(commands.Cog, name='queue'):
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
            game, participant = player.get_last_game_and_participant(self.bot.session)
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
            await ctx.message.add_reaction(chr(127462 + (ord(f"{role[0]}")-97)))

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

    @commands.command(help_index=4)
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

    @commands.command(help_index=5)
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

    @commands.command(help_index=6)
    async def cancel_game(self, ctx: commands.context):
        """
        Cancels and voids your ongoing game. Require validation from other players in the game.
        """
        player = get_player(self.bot.session, ctx)

        game, participant = player.get_last_game_and_participant(self.bot.session)
        game = self.bot.session.query(Game).filter(Game.id == game.id).one()

        # If the game is already done and scored, we don’t offer cancellation anymore.
        if game.winner:
            no_cancel_notice = f'You don’t seem to currently be in a game.\n' \
                      f'If you want to change your last game’s winner, call `!won` or `!lost`.'
            logging.info(no_cancel_notice)
            await ctx.send(no_cancel_notice)
            return

        ready_check_message = await ctx.send('Trying to cancel the game including {}.\n'
                                             'If you want to cancel the game, have at least 6 players press ✅.\n'
                                             'If you did not mean to cancel the game, press ❎.'
                                             .format(
            ', '.join(['<@{}>'.format(p.player) for p in game.participants])),
            delete_after=60)

        await ready_check_message.add_reaction('✅')
        await ready_check_message.add_reaction('❎')

        players_discord_ids = [p.player.discord_id for p in game.participants]

        # TODO Find a way to remove code duplication with ready_check
        def checkmark_reaction_check(received_reaction: discord.Reaction, sending_user: discord.User):
            return received_reaction.message.id == ready_check_message.id and \
                   sending_user.id in players_discord_ids and \
                   str(received_reaction.emoji) in ['✅', '❎']

        cancelling_users = set()
        try:
            while True:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=checkmark_reaction_check)

                if str(reaction.emoji) == '✅':
                    logging.info(f'{user} has accepted to cancel the game.')
                    cancelling_users.add(user.id)
                    if cancelling_users.__len__() == 6:
                        continue

                elif str(reaction.emoji) == '❎':
                    no_cancellation_message = f'{user} has cancelled the cancellation.'
                    logging.info(no_cancellation_message)
                    await ctx.send(no_cancellation_message, delete_after=30)
                    return
        # We get there if no player pressed the checkmark in the last minute, we cancel
        except asyncio.TimeoutError:
            return

        self.bot.session.delete(game)
        self.bot.session.commit()

        cancel_notice = f'Game {game.id} cancelled.'

        logging.info(cancel_notice)
        await ctx.send(cancel_notice)

    @commands.command(help_index=2)
    async def won(self, ctx: commands.context, *args):
        """
        Scores your last game as a win and informs the champion used.

        Optional arguments:
            champion_name   The champion you used in the game (for stats tracking)
                                If the champion name has spaces, use "Miss Fortune" or missfortune
            game_id         The game ID (by default the result is applied to your last game)

        Example usage:
            !won
            !won "Miss Fortune"
            !won mf
            !won missfortune
            !won reksai 10
        """
        await self.score_game(ctx, True)
        await self.update_champion(ctx, args)

    @commands.command(help_index=3)
    async def lost(self, ctx: commands.context, *args):
        """
        Scores your last game as a loss and informs the champion used.

        Optional arguments:
            champion_name   The champion you used in the game (for stats tracking)
                                If the champion name has spaces, use "Miss Fortune" or missfortune
            game_id         The game ID (by default the result is applied to your last game)

        Example usage:
            !won
            !won "Miss Fortune"
            !won mf
            !won missfortune
            !won reksai 10)
        """
        await self.score_game(ctx, False)
        await self.update_champion(ctx, args)

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
            # If ready_check returns False, we restart matchmaking as the queue changed
            self.bot.session.delete(game)
            self.bot.session.commit()
            await self.matchmaking_process(ctx)
            return

        logging.info(f'Starting game {game.id}')

        # Saving the game to the database
        self.bot.session.commit()

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
            .format(', '.join(['<@{}>'.format(p.discord_id) for p in players.values()])), embed=embed)

        await ready_check_message.add_reaction('✅')
        await ready_check_message.add_reaction('❎')

        players_discord_ids = [p.discord_id for p in players.values()]

        def check(received_reaction: discord.Reaction, sending_user: discord.User):
            # This check is simply used to see if a player in the game responded to the message.
            # Queue logic is handled below
            return received_reaction.message.id == ready_check_message.id and \
                   sending_user.id in players_discord_ids and \
                   str(received_reaction.emoji) in ['✅', '❎']

        users_ready = set()
        try:
            while True:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=120.0, check=check)

                if str(reaction.emoji) == '✅':
                    logging.info(f'{user} has accepted the game')

                    users_ready.add(user.id)
                    if users_ready.__len__() == 10:
                        return True

                elif str(reaction.emoji) == '❎':
                    logging.info(f'{user} has cancelled the game')
                    break

        # We get there if no player accepted in the last two minutes
        except asyncio.TimeoutError:
            pass

        await ctx.send('The game has been cancelled. You can queue again.')
        return False

    async def score_game(self, ctx, result: bool):
        """
        Scores the player’s last game with the given result.
        """
        player = get_player(self.bot.session, ctx)

        game, game_participant = player.get_last_game_and_participant(self.bot.session)
        previous_winner = game.winner

        game.winner = 'blue' if game_participant.team == 'blue' and result else 'red'

        if previous_winner and previous_winner != game.winner:
            # Conflict between entered results and current results
            warnings.warn('A player is trying to change a game’s result.')

            warning_message = await ctx.send(f'**⚠️⚠️⚠️ Game result conflict for game {game.id} ⚠️⚠️⚠️**\n'
                                             f'If you really want to change the result, react to the message with ⚠️\n',
                                             delete_after=30)
            await warning_message.add_reaction('⚠️')

            def check(received_reaction: discord.Reaction, sending_user: discord.User):
                return received_reaction.message.id == warning_message.id and \
                       sending_user.id == ctx.author.id and \
                       str(received_reaction.emoji) == '⚠️'

            try:
                await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send('Game result unchanged', delete_after=10)
                return

        elif previous_winner:
            await ctx.send('Your last game has already been scored. Thank you for validating the information!',
                           delete_after=10)
            return

        # If we actually want to process the game’s result, we commit the winner to the database.
        self.bot.session.commit()
        game.update_trueskill(self.bot.session)

        message = f'Game {game.id} has been scored as a win for {game.winner} and ratings have been updated.'

        logging.info(message)
        await ctx.send(message)

    async def update_champion(self, ctx, args):
        if not args:
            return

        champion_id, ratio = self.bot.lit.get_id(args[0], input_type='champion', return_ratio=True)

        if ratio < 75:
            await ctx.send('Champion name was not understood properly.\nUse `!help won` for more information.',
                           delete_after=10)
            return

        player = get_player(self.bot.session, ctx)
        try:
            game, participant = self.bot.session.query(Game, GameParticipant).join(GameParticipant) \
                .filter(Game.id == args[1]) \
                .filter(GameParticipant.player_id == player) \
                .order_by(Game.date.desc()) \
                .first()
        except IndexError:
            game, participant = player.get_last_game_and_participant(self.bot.session)

        participant.champion_id = champion_id
        self.bot.session.merge(participant)

        self.bot.session.commit()

        log_message = f'Champion for game {game.id} set to {self.bot.lit.get_name(participant.champion_id)} for {player.name}'

        logging.info(log_message)
        await ctx.send(log_message, delete_after=10)
