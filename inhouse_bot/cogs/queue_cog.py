import warnings
from collections import defaultdict
import itertools
import logging
import os

import discord
import trueskill
from discord import Embed
from discord.ext import commands
from rapidfuzz import process
from tabulate import tabulate

from inhouse_bot.common_utils import trueskill_blue_side_winrate
from inhouse_bot.sqlite.game import Game
from inhouse_bot.sqlite.game_participant import GameParticipant
from inhouse_bot.sqlite.player import Player
from inhouse_bot.sqlite.player_rating import PlayerRating
from inhouse_bot.sqlite.sqlite_utils import get_session, roles_list


class QueueCog(commands.Cog, name='queue'):
    def __init__(self, bot):
        """
        :param bot: the bot to attach the cog to
        """
        self.bot = bot
        self.channel_queues = defaultdict(lambda: {role: set() for role in roles_list})
        self.session = get_session()

    def get_player(self, ctx) -> Player:
        """
        Returns a Player object from a Discord context’s author and update name changes.
        """
        player = self.session.merge(Player(ctx.author))  # This will automatically update name changes
        self.session.commit()

        return player

    @commands.command(help_index=0)
    async def queue(self, ctx: commands.Context, *, roles):
        """
        Puts you in a queue in the current channel for the specified roles.
        Roles are top, jungle, mid, bot, and support.

        Example usage:
            !queue support
            !queue mid bot
        """
        player = self.get_player(ctx)

        # First, we check if the last game of the player is still ongoing.
        try:
            game, participant = self.get_last(player)
            if not game.winner:
                await ctx.send('Your last game looks to be ongoing. '
                               'Please use !won or !lost to inform the result if the game is over.')
                return
        # This happens if the player has not played a game yet as get_last returns None and can’t be unpacked
        except TypeError:
            pass

        clean_roles = [process.extractOne(r, roles_list)[0] for r in roles.split(' ')]

        for role in clean_roles:
            if role not in player.ratings:
                logging.info('Creating a new PlayerRating for <{}> <{}>'.format(player.discord_string, role))
                new_rating = PlayerRating(player, role)
                self.session.add(new_rating)
                self.session.commit()
                # This step is required so our player object has access to the rating
                player = self.session.merge(player)

            self.channel_queues[ctx.channel.id][role].add(player)
            logging.info('Player <{}> has been added to the <{}> queue'.format(player.discord_string, role))

        await ctx.send('{} is now in queue for {}.'.format(ctx.author, ' and '.join(clean_roles)),
                       embed=self.get_current_queue_embed(ctx))

        await self.matchmake(ctx)

    async def matchmake(self, ctx):
        """
        Start the matchmaking process in the given channel.

        This function is split in multiple functions for easier testing.
        """
        players, match_quality = self.match_game(ctx.channel.id)

        # We have a good match
        if match_quality > -0.1:
            await self.start_game(ctx, players)
        # We have a match that could be slightly one-sided
        elif match_quality > -0.2:
            await self.start_game(ctx, players, mismatch=True)

    def match_game(self, channel_id) -> tuple:
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

            score = -abs(0.5 - trueskill_blue_side_winrate(players))

            if score > best_score:
                best_players = players
                best_score = score

        logging.info('The best match found had a score of {}'.format(best_score))

        return best_players, best_score

    async def start_game(self, ctx, players, mismatch=False):
        """
        Attempts to start the given game by pinging players and waiting for their reactions.
        """
        game = Game(players)

        # TODO Find a cleaner way to handle this test
        if 'PYTEST_CURRENT_TEST' not in os.environ:
            # We wait for all 10 players to be ready before creating the game
            if not self.ready_check(ctx, players, mismatch, game):
                # If ready_check returns False, we restart matchmaking as the queue changed
                await self.matchmake(ctx)
                return

        # Remove all players from all queues before starting the game
        for player in players.values():
            await self.remove_player(player)

        self.session.add(game)
        self.session.commit()

        await ctx.send(f'Game {game.id} has been started!')

    @staticmethod
    async def ready_check(ctx, players, mismatch, game):
        """
        Posts a message in the given context, pinging the 10 players, trying to start the game.

        If all 10 players accept the game, returns True.
        If not, returns False.
        """
        logging.info('Trying to start a game.')

        embed = Embed(title='Proposed game')
        embed.add_field(name='Team compositions',
                        value=f'```{game}```')

        embed.add_field(name='Get ready',
                        value='A match has been found for {}.\n'
                              'You can refuse the match and leave the queue by pressing ❎.\n'
                              'If you are ready, press ✅.'
                        .format(', '.join(['<@{}>'.format(p.discord_id) for p in players.values()])))
        if mismatch:
            embed.add_field(name='WARNING',
                            value='According to TrueSkill, this game might be a slight mismatch.')

        message = await ctx.send(embed=embed)

        await message.add_reaction('✅')
        await message.add_reaction('❎')

        # TODO Use wait_for to react to the emotes
        # Reacting with '✅' checks if all 10 players have reacted and are ready.
        # Reacting with ❎ removes you from the queue in the current channel and restarts matchmaking.

        return True

    @commands.command(help_index=1)
    async def leave_queue(self, ctx: commands.Context, *args):
        """
        Removes you from the queue in the current channel or all channels with !stop_queue all.

        Example usage:
            !stop_queue
            !stop_queue all
        """
        player = self.get_player(ctx)

        await self.remove_player(player, ctx.channel.id if args else None, ctx)

    async def remove_player(self, player, channel_id=None, ctx=None):
        """
        Removes the given player from queue.

        If given a channel_id, only removes the player from the given channel.
        If given a context, posts a notice in it.
        """
        for channel_id in self.channel_queues if not channel_id else channel_id:
            for role in self.channel_queues[channel_id]:
                self.channel_queues[channel_id][role].discard(player)

        logging.info('Player <{}> has been removed from {}'
                     .format(player.discord_string,
                             'all queues' if not channel_id else 'the <{}> queue'.format(channel_id)))

        if ctx:
            await ctx.send('{} has been removed from the queue{}'
                           .format(ctx.author, ' in all channels' if channel_id else ''),
                           embed=self.get_current_queue_embed(ctx))

    @commands.command(help_index=4)
    async def view_queue(self, ctx: commands.Context):
        """
        Shows the active queue in the channel.
        """
        await ctx.send(embed=self.get_current_queue_embed(ctx))

    def get_current_queue_embed(self, ctx):
        table = [[]]
        for role in roles_list:
            table.append([role.capitalize()] + [p.name for p in self.channel_queues[ctx.channel.id][role]])

        embed = Embed(title='Current queue', colour=discord.colour.Colour.dark_red())
        embed.add_field(name='Queue', value=f'```{tabulate(table, tablefmt="plain")}```')

        return embed

    @commands.command(help_index=5)
    async def view_games(self, ctx: commands.context):
        """
        Shows the ongoing inhouse games.
        """
        games_without_results = self.session.query(Game).filter(Game.winner == None).all()

        if not games_without_results:
            await ctx.send('No active games found')
            return

        embed = Embed(title='Ongoing games', colour=discord.colour.Colour.dark_blue())
        for game in games_without_results:
            embed.add_field(name=f'Game {game.id}',
                            value=f'```{game}```')

        await ctx.send(embed=embed)

    # TODO Check if we need to restrict access to this function
    @commands.command(help_index=6)
    async def cancel_game(self, ctx: commands.context, game_id):
        """
        Cancels and voids an ongoing game. Requires the game id from !view_games.
        """
        game = self.session.query(Game).filter(Game.id == game_id).one()

        self.session.delete(game)
        self.session.commit()

        message = f'Game {game.id} cancelled.'

        logging.info(message)
        await ctx.send(message)

    @commands.command(help_index=2)
    async def won(self, ctx: commands.context, *args):
        """
        Scores the game as a win for your team.

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
        self.update_champion(ctx, args)

    @commands.command(help_index=3)
    async def lost(self, ctx: commands.context, *args):
        """
        Scores the game as a loss for your team.

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
        await self.score_game(ctx, False)
        await self.update_champion(ctx, args)

    async def score_game(self, ctx, result):
        player = self.get_player(ctx)

        game, game_participant = self.get_last(player)
        previous_winner = game.winner

        game.winner = 'blue' if game_participant.team == 'blue' and result else 'red'

        if previous_winner and previous_winner != game.winner:
            # Conflict between entered results and current results
            warnings.warn('A player is trying to change a game’s result.')
            # TODO Implement conflict resolution here (which will require recomputing TrueSkill from this game)
            await ctx.send(f'**/!\\ Game result conflict for game {game.id}.**')
            # await ctx.send('**/!\\ TrueSkill ratings will be recomputed starting from this game**')
        elif previous_winner:
            ctx.send('This game has already been scored. Thank you for validating the information!')
            return

        self.session.commit()
        self.update_trueskill(game)

        message = f'Game {game.id} has been scored as a win for {game.winner} and ratings have been updated.'

        logging.info(message)
        await ctx.send(message)

    async def update_champion(self, ctx, args):
        if not args:
            return

        champion_id, ratio = self.bot.lit.get_id(args[0], input_type='champion', return_ratio=True)

        if ratio < 75:
            await ctx.send('Champion name was not understood properly.\nUse `!help won` for more information.')
            return

        player = self.get_player(ctx)
        try:
            game, participant = self.session.query(Game, GameParticipant).join(GameParticipant) \
                .filter(Game.id == args[1]) \
                .filter(GameParticipant.player_id == player) \
                .order_by(Game.date.desc()) \
                .first()
        except IndexError:
            game, participant = self.get_last(player)

        participant.champion_id = champion_id
        self.session.merge(participant)

        self.session.commit()

        logging.info(f'Champion for game {game.id} set to {self.bot.lit.get_name(participant.champion_id)} '
                     f'for {ctx.author}')
        await ctx.send(f'Champion for game {game.id} set to {self.bot.lit.get_name(participant.champion_id)}')

    def get_last(self, player: Player):
        """
        Returns the last game and game_participant for the given user.
        """
        return self.session.query(Game, GameParticipant).join(GameParticipant) \
            .filter(GameParticipant.player_id == player.discord_id) \
            .order_by(Game.date.desc()) \
            .first()

    def update_trueskill(self, game):
        """
        Updates the game’s participants TrueSkill values based on the game result.
        """
        # participant.trueskill represents pre-game values
        # p.player.ratings[p.role] is the PlayerRating relevant to the game that was scored
        team_ratings = {team: {p.player.ratings[p.role]: trueskill.Rating(p.trueskill_mu, p.trueskill_sigma)
                               for p in game.participants.values() if p.team == team}
                        for team in ['blue', 'red']}

        if game.winner == 'blue':
            new_ratings = trueskill.rate([team_ratings['blue'], team_ratings['red']])
        else:
            new_ratings = trueskill.rate([team_ratings['red'], team_ratings['blue']])

        for team in new_ratings:
            for player_rating in team:
                player_rating.trueskill_mu = team[player_rating].mu
                player_rating.trueskill_sigma = team[player_rating].sigma
                self.session.add(player_rating)

        self.session.commit()
