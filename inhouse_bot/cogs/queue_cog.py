from discord.ext import commands


class QueueCog(commands.Cog, name='queue'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def queue(self, ctx: commands.Context):
        await ctx.send('TODO QUEUE FUNCTION')
