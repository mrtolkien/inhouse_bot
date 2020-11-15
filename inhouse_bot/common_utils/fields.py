from discord.ext import commands
from discord.ext.commands import ConversionError
from sqlalchemy import Enum
import rapidfuzz
import lol_id_tools

roles_list = ["TOP", "JGL", "MID", "BOT", "SUP"]
role_enum = Enum(*roles_list, name="role_enum")

side_enum = Enum("BLUE", "RED", name="team_enum")

foreignkey_cascade_options = {"onupdate": "CASCADE", "ondelete": "CASCADE"}

# This is a dict used for fuzzy matching
full_roles_dict = {
    "top": "TOP",
    "jgl": "JGL",
    "jungle": "JGL",
    "jungler": "JGL",
    "mid": "MID",
    "bot": "BOT",
    "adc": "BOT",
    "sup": "SUP",
    "supp": "SUP",
    "support": "SUP",
}

class MultiRoleConverter(commands.Converter):
    async def convert_role(self, ctx, argument):
        """
        Converts an input string to a clean role
        """
        await ctx.send("1")
        matched_string, ratio = rapidfuzz.process.extractOne(argument, full_roles_dict.keys())
        await ctx.send("2")
        if ratio < 85:
            await ctx.send(f"The role was not understood")
            raise ConversionError

        else:
            return full_roles_dict[matched_string]

    async def convert(self, ctx, argument):
        """
        Converts an input string to a clean role
        """
        roles = str(argument).split(',')
        
        converted_roles = []
        for role in roles:
            converted_roles.append(self.convert_role(ctx, role))
            await ctx.send(role
            )
        return converted_roles


class ChampionNameConverter(commands.Converter):
    async def convert(self, ctx, argument):
        """
        Converts an input string to a clean champion ID
        """
        try:
            return lol_id_tools.get_id(argument, input_locale="en_US", object_type="champion")

        except lol_id_tools.NoMatchingNameFound:
            await ctx.send(f"The champion name was not understood")
            raise ConversionError
