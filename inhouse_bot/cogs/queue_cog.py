from collections import defaultdict, Counter
import itertools

import discord
from discord import Embed
from discord.ext import commands
from rapidfuzz import process
from tabulate import tabulate

from inhouse_bot.cogs.cog_utilities import get_player
from inhouse_bot.common_utils import trueskill_blue_side_winrate
from inhouse_bot.sqlite.game import Game
from inhouse_bot.sqlite.game_participant import GameParticipant
from inhouse_bot.sqlite.player import Player
from inhouse_bot.sqlite.sqlite_utils import get_session, roles_list


class QueueCog(commands.Cog, name='queue'):
    def __init__(self, bot):
        self.bot = bot
        self.channel_queues = defaultdict(lambda: {role: set() for role in roles_list})
        self.session = get_session()

    @commands.command()
    async def queue(self, ctx: commands.Context, *, roles):
        """
        Puts you in a queue in the current channel for the specified roles.
        Roles are top, jungle, mid, bot, and support

        Example usage:
            !queue support
            !queue mid bot
        """
        player = get_player(ctx)

        # First, we check if the last game of the player is still ongoing.
        game, participant = self.get_last(player)

        if not game.winner:
            await ctx.send('Your last game is still ongoing. Please use !won or !lost to inform the result.')
            return

        clean_roles = [process.extractOne(r, roles_list)[0] for r in roles.split(' ')]

        for role in clean_roles:
            self.channel_queues[ctx.channel.id][role].add(player)

        await ctx.send('{} is now in queue for {}.'.format(ctx.author, ' and '.join(clean_roles)),
                       embed=self.get_current_queue_embed(ctx))

        players, match_quality = self.match_game(ctx.channel.id)

        # We have a good match
        if match_quality > -0.1:
            self.start_game(ctx, players)
        # We have a match that could be slightly one-sided
        elif match_quality > -0.2:
            self.start_game(ctx, players, mismatch=True)

    def match_game(self, channel_id) -> tuple:
        """
        Looks at the queue in the channel and returns the best match-made game and its "quality".
        """
        # Do not do anything if there’s not at least 2 players in queue per role
        for role in roles_list:
            if self.channel_queues[channel_id][role].__len__() < 2:
                return None, -1

        # We use a list of [(player, team, role)] -> match making quality
        matches_quality = Counter()

        # Simply testing all permutations because it should be pretty lightweight
        role_permutations = []
        for role in roles_list:
            role_permutations.append([p for p in itertools.permutations(self.channel_queues[channel_id][role], 2)])

        for team_composition in itertools.product(*role_permutations):
            # players: [team, role] -> Player
            players = {('red' if tuple_idx else 'blue', roles_list[role_idx]): players_tuple[tuple_idx]
                       for role_idx, players_tuple in enumerate(team_composition)
                       for tuple_idx in (0, 1)}
            # We check to make sure all 10 players are different
            if set(players.values()).__len__() != 10:
                continue
            matches_quality[players] = -abs(0.5 - trueskill_blue_side_winrate(players))

        return matches_quality.most_common(1)[0]

    def start_game(self, ctx, players, mismatch=False):
        game = Game(players)

        embed = Embed(title='Proposed game')
        embed.add_field(name='Team compositions',
                        value='```{}```'.format(str(game)))

        embed.add_field(name='Get ready',
                        value='A match has been found.\n'
                              'You can refuse the match and leave the queue by pressing :negative_squared_cross_mark:.\n'
                              'If you are ready, press :white_check_mark:.')
        if mismatch:
            embed.add_field(name='WARNING',
                            value='According to TrueSkill, this game might be a slight mismatch.')

        message = await ctx.send(embed=embed)

        # TODO Use wait_for to react to the emotes

        game_start = False
        if game_start:
            self.remove_players_from_queue(players)


    @commands.command()
    async def stop_queue(self, ctx: commands.Context, *args):
        """
        Removes you from the queue in the current channel or all channels with !stop_queue all.

        Example usage:
            !stop_queue
            !stop_queue all
        """
        for channel_id in self.channel_queues if args else [ctx.channel.id]:
            for role in self.channel_queues[channel_id]:
                self.channel_queues[channel_id][role].discard(get_player(ctx))

        await ctx.send('{} has been removed from the queue{}'.format(ctx.author, ' in all channels' if args else ''),
                       embed=self.get_current_queue_embed(ctx))

    @commands.command()
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
        embed.add_field(name='Queue', value='```{}```'.format(tabulate(table, tablefmt='plain')))

        return embed

    @commands.command()
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
            embed.add_field(name='Game {}'.format(game.id),
                            value='```{}```'.format(str(game)))

        await ctx.send(embed=embed)

    # TODO Check if we restrict access to this function
    @commands.command()
    async def cancel_game(self, ctx: commands.context, game_id):
        """
        Cancels and voids an ongoing game. Requires the game id from !view_games.
        """
        game = self.session.query(Game).filter(Game.id == game_id).one()

        self.session.delete(game)
        self.session.commit()

        await ctx.send('Game {} cancelled.'.format(game.id))

    @commands.command()
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
        self.score_game(ctx, True)
        self.update_champion(ctx, args)

    @commands.command()
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

        self.score_game(ctx, False)
        self.update_champion(ctx, args)

    def score_game(self, ctx, result):
        game, game_participant = self.get_last(get_player(ctx))

        previous_winner = game.winner

        game.winner = 'blue' if game_participant.team == 'blue' and result else 'red'

        if previous_winner and previous_winner != game.winner:
            # Conflict between entered results and current results
            # TODO Add a validation here?
            await ctx.send('**/!\ Game result changed for game {}**'.format(game.id))
            await ctx.send('**/!\ TrueSkill ratings will be recomputed starting from this game**'.format(game.id))

        self.update_trueskill(game)

    def update_champion(self, ctx, args):
        if not args:
            return

        champion_id, ratio = self.bot.lit.get_id(args[0], input_type='champion', return_ratio=True)

        if ratio < 75:
            ctx.send('Champion name was not understood properly.\nUse `!help won` for more information.')
            return

        player = get_player(ctx)
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

        ctx.send('Champion for game {} set to {}'.format(game.id, self.bot.lit.get_name(participant.champion_id)))

    def get_last(self, player: Player):
        """
        Returns the last game and game_participant for the given user.
        """
        return self.session.query(Game, GameParticipant).join(GameParticipant) \
            .filter(GameParticipant.player_id == player.discord_id) \
            .order_by(Game.date.desc()) \
            .first()

    def update_trueskill(self, game):
        # TODO Update trueskill values for PlayerRating objects, based on the game’s result.
        pass

    def remove_players_from_queue(self, players):
        """
        Removes a given list of players from all queues across all channels.
        Mostly used after a match has been made.
        """

        pass
