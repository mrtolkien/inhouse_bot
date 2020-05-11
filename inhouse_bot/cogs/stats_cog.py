from discord.ext import commands
from sqlalchemy import func
from inhouse_bot.cogs.cogs_utils import get_player
from inhouse_bot.sqlite.game_participant import GameParticipant


class StatsCog(commands.Cog, name='stats'):
    def __init__(self, bot: commands.Bot):
        """
        :param bot: the bot to attach the cog to
        """
        self.bot = bot

    @commands.command(help_index=1, aliases=['ratings', 'rating', 'MMR'])
    async def mmr(self, ctx: commands.Context):
        """
        Returns your MMR for all roles.
        """
        player = get_player(self.bot.session, ctx)

        player_games_count = {row.role: row.games for row in
                              self.bot.session
                                  .query(GameParticipant.role, func.count().label('games')) \
                                  .filter(GameParticipant.player_id == player.discord_id) \
                                  .group_by(GameParticipant.role) \
                                  .all()}

        text_lines = []
        for role in player.ratings:
            rating = player.ratings[role]
            try:
                text_lines.append(f'{player.name}’s rating for {rating.role} is '
                                  f'{rating.trueskill_mu - 3 * rating.trueskill_sigma:.1f} '
                                  f'over {player_games_count[role] or 0} games')
            except KeyError:
                continue

        await ctx.send('\n'.join(text_lines) or 'No ratings found')

