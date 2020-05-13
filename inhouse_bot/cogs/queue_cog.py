import asyncio
from collections import defaultdict
import itertools
import logging
from typing import List, Tuple

import discord
from discord import Embed
from discord.ext import commands
from rapidfuzz import process
from tabulate import tabulate
from inhouse_bot.common_utils import trueskill_blue_side_winrate
from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.sqlite.game import Game
from inhouse_bot.sqlite.game_participant import GameParticipant
from inhouse_bot.sqlite.player import Player
from inhouse_bot.sqlite.player_rating import PlayerRating
from inhouse_bot.sqlite.sqlite_utils import roles_list, get_session


class QueueCog(commands.Cog, name='Queue'):
    def __init__(self, bot: InhouseBot):
        """
        :param bot: the bot to attach the cog to
        """
        self.bot = bot
        # [channel_id][role][list of Player objects]
        self.channel_queues = defaultdict(lambda: {role: set() for role in roles_list})

        # [channel_id][message]
        self.latest_queue_message = {}

        # (discord_id)
        self.games_in_ready_check = set()

    @commands.command(help_index=0)
    async def queue(self, ctx: commands.Context, *, roles):
        """
        Puts you in a queue in the current channel for the specified roles.
        Roles are top, jungle, mid, bot, and support.

        Example usage:
            !queue support
            !queue mid bot
        """
        player = await self.bot.get_player(ctx)

        # First, we check if the last game of the player is still ongoing.
        try:
            game, participant = player.get_last_game()
            if not game.winner:
                await ctx.send('Your last game looks to be ongoing. '
                               'Please use !won or !lost to inform the result if the game is over.',
                               delete_after=self.bot.short_notice_duration)
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
            await ctx.send(self.bot.role_not_understood, delete_after=self.bot.warning_duration)
            return

        for role in clean_roles:
            self.add_player_to_queue(player, role, ctx.channel.id)

        for role in clean_roles:
            # Dirty code to get the emoji related to the letters
            await ctx.message.add_reaction(chr(127462 + (ord(f"{role[0]}") - 97)))

        await self.send_queue(ctx)

        await self.matchmaking_process(ctx)

    @commands.command(help_index=1, aliases=['leave'])
    async def leave_queue(self, ctx: commands.Context, *args):
        """
        Removes you from the queue in the current channel or all channels with !stop_queue all.

        Example usage:
            !stop_queue
            !stop_queue all
        """
        player = await self.bot.get_player(ctx)

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
            await ctx.send('Champion name was not understood properly.\n'
                           'Use `!help champion` for more information.',
                           delete_after=self.bot.warning_duration)
            return

        player = await self.bot.get_player(ctx)
        session = get_session()

        if game_id:
            game, participant = session.query(Game, GameParticipant).join(GameParticipant) \
                .filter(Game.id == game_id) \
                .filter(GameParticipant.player_id == player.discord_id) \
                .order_by(Game.date.desc()) \
                .first()
        else:
            game, participant = player.get_last_game()

        participant.champion_id = champion_id

        session.merge(participant)
        session.commit()

        log_message = f'Champion for game {game.id} set to {self.bot.lit.get_name(participant.champion_id)} for {player.name}'

        logging.info(log_message)
        await ctx.send(log_message, delete_after=self.bot.short_notice_duration)

    @commands.command(help_index=5, aliases=['view'])
    async def view_queue(self, ctx: commands.Context):
        """
        Shows the active queue in the channel.
        """
        await self.send_queue(ctx)

    @commands.command(help_index=6)
    async def view_games(self, ctx: commands.context):
        """
        Shows the ongoing inhouse games.
        """
        session = get_session()

        games_without_results = session.query(Game).filter(Game.winner == None).all()

        if not games_without_results:
            await ctx.send('No active games found', delete_after=self.bot.short_notice_duration)
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
        player = await self.bot.get_player(ctx)

        session = get_session()
        game, participant = player.get_last_game()

        # If the game is already done and scored, we don’t offer cancellation anymore.
        if game.winner:
            no_cancel_notice = f'You don’t seem to currently be in a game.'
            logging.info(no_cancel_notice)
            await ctx.send(no_cancel_notice)
            return

        discord_ids_list = [p.player.discord_id for p in game.participants.values()]

        cancelling_game_message = await ctx.send(
            f'Trying to cancel the game including {self.get_tags(discord_ids_list)}.\n'
            'If you want to cancel the game, have at least 6 players press ✅.\n'
            'If you did not mean to cancel the game, press ❎.',
            delete_after=self.bot.validation_duration)

        cancel, cancelling_players = await self.checkmark_validation(cancelling_game_message, discord_ids_list, 6)

        if not cancel:
            # If there’s no validation, we just inform players nothing happened and leave
            no_cancellation_message = f'Cancellation canceled.'
            logging.info(no_cancellation_message)
            await ctx.send(no_cancellation_message, delete_after=30)
            return

        # If we get here, 6+ players accepted to cancel the game
        session.delete(game)
        session.commit()

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
        session = get_session()
        game = session.query(Game).filter(Game.id == game_id).one()

        if game.winner:
            await ctx.send(
                'It is currently impossible the change the result of a game that was scored because it would '
                'create huge issues with rating recalculations.')
            return

        if winning_team not in ['blue', 'red']:
            await ctx.send('The winning team must be blue or red.\n'
                           'Example: `!admin_score 1 blue`')
            return

        game.winner = winning_team

        session.commit()
        game.update_trueskill(session)

        message = f'Game {game.id} has been scored as a win for {game.winner} and ratings have been updated.'

        logging.info(message)
        await ctx.send(message)

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def admin_queue(self, ctx, user_id, role):
        """
        Admin-only way to queue a specified user.

        user_id is the player’s discord user id (right click -> Copy ID after enabling discord developer tools)
        role can be any of the valid roles or 'kick'

        Example:
            !admin_queue 127200016472211456 mid
            !admin_queue 127200016472211456 kick
        """
        # This needs to use the players_session to work with player objects equality
        player = self.bot.players_session.query(Player).get(user_id) \
                 or await self.bot.get_player(None, user_id)

        if role == 'kick':
            await self.remove_player_from_queue(player, ctx.channel.id)
        else:
            clean_role, score = process.extractOne(role, roles_list)
            self.add_player_to_queue(player, clean_role, ctx.channel.id)

        await self.send_queue(ctx)

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def reset_queue(self, ctx):
        """
        Admin-only way to reset the queue in the current channel
        """
        self.channel_queues[ctx.channel.id] = {role: set() for role in roles_list}
        await self.send_queue(ctx)

    def add_player_to_queue(self, player, role, channel_id):
        if role not in player.ratings:
            logging.info('Creating a new PlayerRating for <{}> <{}>'.format(player.discord_string, role))
            new_rating = PlayerRating(player, role)
            self.bot.players_session.add(new_rating)
            self.bot.players_session.commit()
            # This step is required so our player object has access to the rating
            player = self.bot.players_session.merge(player)

        # Actually adding the player to the queue
        self.channel_queues[channel_id][role].add(player)
        logging.info(f'Player <{player.discord_string}> has been added to the <{role}><{channel_id}> queue')

    async def send_queue(self, ctx: commands.context):
        """
        Deletes the previous queue message and sends a new one in the channel
        """
        channel_id = ctx.channel.id

        try:
            old_queue_message = self.latest_queue_message[channel_id]
        except KeyError:
            old_queue_message = None

        table = [[]]
        for role in roles_list:
            table.append([role.capitalize()] + sorted([p.name for p in self.channel_queues[channel_id][role]]))

        embed = Embed(colour=discord.colour.Colour.dark_red())
        embed.add_field(name='Queue', value=f'```{tabulate(table, tablefmt="plain")}```')

        self.latest_queue_message[channel_id] = await ctx.send(embed=embed)

        # Sequenced that way for smoother scrolling in discord
        if old_queue_message:
            await old_queue_message.delete()

    async def remove_player_from_queue(self, player, channel_id=None, ctx=None) -> List[Tuple[int, str]]:
        """
        Removes the given player from queue.

        If given a channel_id, only removes the player from the given channel.
        If given a context message, thumbs ups it.

        Returns a list of [channel_id, role] it was removed from
        """
        channels_roles_list = []

        for channel_id in self.channel_queues if not channel_id else [channel_id]:
            for role in self.channel_queues[channel_id]:
                if player in self.channel_queues[channel_id][role]:
                    channels_roles_list.append((channel_id, role))
                    self.channel_queues[channel_id][role].remove(player)

        logging.info('Player <{}> has been removed from {}'
                     .format(player.discord_string,
                             'all queues' if not channel_id else 'the <{}> queue'.format(channel_id)))

        if ctx:
            await ctx.message.add_reaction('👍')
            await self.send_queue(ctx)

        return channels_roles_list

    async def matchmaking_process(self, ctx):
        """
        Start the matchmaking process in the given channel.

        This function is split in multiple functions for easier testing.
        """
        # Match quality returns -1 when matchmaking has not found a valid game
        players, match_quality = self.find_best_game(ctx.channel.id)

        # We have a good match
        if match_quality > -0.1:
            await self.start_game(ctx, players)
        # We have a match that could be slightly one-sided
        elif match_quality > -0.2:
            await self.start_game(ctx, players, mismatch=True)

    def find_best_game(self, channel_id) -> Tuple[dict, int]:
        """
        Looks at the queue in the channel and returns the best match-made game (as a {team, role} -> Player dict).
        """
        # Do not do anything if there’s not at least 2 players in queue per role
        for role in roles_list:
            if self.channel_queues[channel_id][role].__len__() < 2:
                logging.debug('Not enough players to start matchmaking')
                return {}, -1

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
        players_queues = {}
        for player in players.values():
            players_queues[player.discord_id] = await self.remove_player_from_queue(player, channel_id=ctx.channel.id)

        game_session = get_session()
        game = Game(players)
        game_session.add(game)
        game_session.commit()

        ready, ready_players = await self.ready_check(ctx, players, mismatch, game)

        if not ready:
            # If the ready check fails, we delete the game and let !queue handle restarting matchmaking.
            for player_id in ready_players:
                for queue, role in players_queues[player_id]:
                    self.add_player_to_queue(await self.bot.get_player(None, player_id), role, queue)

            await ctx.send(f'The game has been cancelled.\n'
                           f'Players who pressed ✅ have been put back in queue.\n'
                           f'{self.get_tags([discord_id for discord_id in players_queues if discord_id not in ready_players])}'
                           f' have been removed from queue.')

            game_session.delete(game)
            game_session.commit()

            # We return and restart matchmaking with the new queue
            await self.send_queue(ctx)
            return await self.matchmaking_process(ctx)

        validation_message = f'Game {game.id} has been accepted and can start!'

        logging.info(validation_message)
        await ctx.send(validation_message)

    async def ready_check(self, ctx: commands.Context, players, mismatch, game):
        """
        Posts a message in the given context, pinging the 10 players, trying to start the game.

        If all 10 players accept the game, returns True.
        If not, returns False.
        """
        self.games_in_ready_check.add(game.id)

        logging.info('Starting a game ready check')

        blue_win_chance = trueskill_blue_side_winrate({(team, role): game.participants[team, role].player
                                                       for team, role in game.participants})

        embed = Embed(title='Proposed game')
        embed.add_field(name='Team compositions',
                        value=f'Blue side expected winrate is {blue_win_chance * 100:.1f}%.\n'
                              f'```{game}```')

        if mismatch:
            embed.add_field(name='WARNING',
                            value='According to TrueSkill, this game might be a slight mismatch.')

        discord_id_list = [p.discord_id for p in players.values()]

        ready_check_message = await ctx.send(f'A match has been found for {self.get_tags(discord_id_list)}.\n'
                                             'All players have been dropped from queues they were in.\n'
                                             'You can refuse the match and leave the queue by pressing ❎.\n'
                                             'If you are ready, press ✅.', embed=embed)

        return_value, accepting_players = await self.checkmark_validation(ready_check_message, discord_id_list, 10)

        self.games_in_ready_check.remove(game.id)

        return return_value, accepting_players

    async def score_game(self, ctx, result: bool):
        """
        Scores the player’s last game with the given result.
        """
        player = await self.bot.get_player(ctx)

        game, game_participant = player.get_last_game()

        if game.winner or game.id in self.games_in_ready_check:
            # Conflict between entered results and current results
            await ctx.send(f'**Your last game’s result was already entered and validated**', delete_after=30)
            return

        winner = 'blue' if (game_participant.team == 'blue' and result) else 'red'

        discord_id_list = [p.player_id for p in game.participants.values()]

        ready_check_message = await ctx.send(f'{player.name} wants to score game {game.id} as a win for {winner}.\n'
                                             f'{self.get_tags(discord_id_list)}.\n'
                                             f'Result will be validated once 6 players from the game press ✅.')

        score_ok, scoring_players = await self.checkmark_validation(ready_check_message, discord_id_list, 6)

        if not score_ok:
            await ctx.send('Game result input cancelled.', delete_after=self.bot.warning_duration)
            await ready_check_message.delete()
            return

        game.winner = winner
        game.update_trueskill()

        message = f'Game {game.id} has been scored as a win for {game.winner} and ratings have been updated.'

        logging.info(message)
        await ctx.send(message)

    async def checkmark_validation(self, message: discord.Message,
                                   validating_members: [],
                                   validation_threshold: int,
                                   timeout=120.0) -> Tuple[bool, set]:
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
                        return True, members_who_validated

                elif str(reaction.emoji) == '❎':
                    break

        # We get there if no player accepted in the last two minutes
        except asyncio.TimeoutError:
            pass

        # This handles both timeout and queue refusal
        return False, members_who_validated

    @staticmethod
    def get_tags(discord_ids: list):
        return ', '.join(['<@{}>'.format(discord_id) for discord_id in discord_ids])
