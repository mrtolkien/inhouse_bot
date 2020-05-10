import asyncio
import warnings
from collections import defaultdict
import itertools
import logging
import os

import discord
import trueskill
from discord import Embed, Emoji
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
    def __init__(self, bot: commands.Bot):
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
            await ctx.message.add_reaction(chr(127462 + (ord(f"{role[0]}")-97)))

        await self.matchmake(ctx)

    def add_player_to_queue(self, player, role, channel_id):
        if role not in player.ratings:
            logging.info('Creating a new PlayerRating for <{}> <{}>'.format(player.discord_string, role))
            new_rating = PlayerRating(player, role)
            self.session.add(new_rating)
            self.session.commit()
            # This step is required so our player object has access to the rating
            player = self.session.merge(player)

        # Actually adding the player to the queue
        self.channel_queues[channel_id][role].add(player)
        logging.info(f'Player <{player.discord_string}> has been added to the <{role}><{channel_id}> queue')

    async def matchmake(self, ctx):
        """
        Start the matchmaking process in the given channel.

        This function is split in multiple functions for easier testing.
        """
        # Match quality returns -1 when matchmaking can’t be done
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
        # TODO To do that, navigate per role?
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
        # Start by removing all players from the channel queue before starting the game
        for player in players.values():
            await self.remove_player_from_queue(player, channel_id=ctx.channel.id)

        game = Game(players)

        if not await self.ready_check(ctx, players, mismatch, game):
            # If ready_check returns False, we restart matchmaking as the queue changed
            await self.matchmake(ctx)
            return

        logging.info(f'Starting game {game.id}')

        # Saving the game to the database
        self.session.add(game)
        self.session.commit()

        await ctx.send(f'Game {game.id} has started!')

    async def ready_check(self, ctx: commands.Context, players, mismatch, game):
        """
        Posts a message in the given context, pinging the 10 players, trying to start the game.

        If all 10 players accept the game, returns True.
        If not, returns False.
        """
        # TODO Find a cleaner way to handle this test with a mock
        if 'PYTEST_CURRENT_TEST' in os.environ:
            return True

        logging.info('Starting a game ready check.')

        # TODO Clean up the code duplication between this and str(game)
        table = tabulate({team_column: [players[team, role].name
                                         for (team, role) in players if team == team_column]
                           for team_column in ['blue', 'red']}, headers='keys')

        embed = Embed(title='Proposed game')
        embed.add_field(name='Team compositions',
                        value=f'```{table}```')

        if mismatch:
            embed.add_field(name='WARNING',
                            value='According to TrueSkill, this game might be a slight mismatch.')

        ready_check_message = await ctx.send('A match has been found for {}.\n'
                                             'You can refuse the match and leave the queue by pressing ❎.\n'
                                             'If you are ready, press ✅.'
            .format(
            ', '.join(['<@{}>'.format(p.discord_id) for p in players.values()])), embed=embed)

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
                    # Put all other players back in the queue and return
                    # TODO Properly queue you back in the roles
                    for team, role in players:
                        if players[(team, role)].discord_id != user.id:
                            self.add_player_to_queue(players[(team, role)], role, ctx.channel.id)
                    return False

        # We get there if no player accepted in the last two minutes
        except asyncio.TimeoutError:
            await ctx.send('No player accepted the match in the last two minutes. '
                           'Removing afk players from all queues and restarting matchmaking.',
                           delete_after=30)
            for team, role in players:
                if players[(team, role)].discord_id in users_ready:
                    self.add_player_to_queue(players[(team, role)], role, ctx.channel.id)
            return False

    @commands.command(help_index=1)
    async def leave_queue(self, ctx: commands.Context, *args):
        """
        Removes you from the queue in the current channel or all channels with !stop_queue all.

        Example usage:
            !stop_queue
            !stop_queue all
        """
        player = self.get_player(ctx)

        await self.remove_player_from_queue(player, ctx.channel.id if not args else None, ctx)

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

    @commands.command(help_index=4)
    async def view_queue(self, ctx: commands.Context):
        """
        Shows the active queue in the channel.
        """
        await ctx.send(embed=self.get_current_queue_embed(ctx))

    def get_current_queue_embed(self, ctx):
        table = [[]]
        for role in roles_list:
            table.append([role.capitalize()] + sorted([p.name for p in self.channel_queues[ctx.channel.id][role]]))

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
            await ctx.send('No active games found', delete_after=10)
            return

        embed = Embed(title='Ongoing games', colour=discord.colour.Colour.dark_blue())
        for game in games_without_results:
            embed.add_field(name=f'Game {game.id}',
                            value=f'```{game}```')

        await ctx.send(embed=embed)

    @commands.command(help_index=6)
    @commands.has_permissions(administrator=True)
    async def cancel_game(self, ctx: commands.context, game_id):
        """
        Cancels and voids an ongoing game. Requires the game id from !view_games.

        Accessible only by server admins.
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
        await self.update_champion(ctx, args)

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
            await ctx.send(f'**⚠️⚠️⚠️ Game result conflict for game {game.id} ⚠️⚠️⚠️**')
            await ctx.send(f'**TODO**')
            return
            # await ctx.send('**/!\\ TrueSkill ratings will be recomputed starting from this game**')
        elif previous_winner:
            await ctx.send('Your last game has already been scored. Thank you for validating the information!',
                           delete_after=10)
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
            await ctx.send('Champion name was not understood properly.\nUse `!help won` for more information.',
                           delete_after=10)
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

        log_message = f'Champion for game {game.id} set to {self.bot.lit.get_name(participant.champion_id)} for {ctx.author}'

        logging.info(log_message)
        await ctx.send(log_message, delete_after=10)

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
