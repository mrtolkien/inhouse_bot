import asyncio
import logging
from typing import Tuple, Optional, List, Set

import discord
from discord.ext.commands import Bot

from inhouse_bot.queue_channel_handler import queue_channel_handler


checkmark_logger = logging.getLogger("inhouse_bot_validation")


async def checkmark_validation(
    bot: Bot,
    message: discord.Message,
    validating_players_ids: List[int],
    validation_threshold: int = 10,
    timeout=120,
    game=None,
) -> Tuple[Optional[bool], Optional[Set[int]]]:
    """
    Implements a checkmark validation on the chosen message.

    If given a game object, will update the message’s embed with validation marks

    3 possible outcomes:
        True and None
            It was validated by the necessary number of players
        False with the the player who cancelled (in a list)
            It was cancelled and the player should be dropped
        None with a list of players who did not validate
            It timed out and the players who didn't validate should be dropped
    """
    checkmark_logger.info(
        f"Starting validation message {message.id} with threshold {validation_threshold}"
        f" for players {' '.join(str(i) for i in validating_players_ids)}"
    )

    queue_channel_handler.mark_queue_related_message(message)

    await message.add_reaction("✅")
    await message.add_reaction("❌")

    def check(received_reaction: discord.Reaction, sending_user: discord.User):
        # This check is simply used to see if a player in the game responded to the message.
        return (
            received_reaction.message.id == message.id
            and sending_user.id in validating_players_ids
            and str(received_reaction.emoji) in ["✅", "❌"]
        )

    ids_of_players_who_validated = set()

    # Default values that will be output in case of success
    result = True
    ids_to_drop = None
    try:
        while len(ids_of_players_who_validated) < validation_threshold:
            reaction, user = await bot.wait_for("reaction_add", timeout=timeout, check=check)

            # A player accepted, we keep him in memory
            if str(reaction.emoji) == "✅":
                ids_of_players_who_validated.add(user.id)

                checkmark_logger.info(f"Player {user.id} validated")

                if game:
                    await message.edit(
                        embed=game.get_embed(
                            embed_type="GAME_FOUND", validated_players=ids_of_players_who_validated, bot=bot
                        )
                    )

            # A player cancels, we return it and will drop him
            elif str(reaction.emoji) == "❌":
                checkmark_logger.info(f"Player {user.id} cancelled, exiting validation")

                result, ids_to_drop = False, {user.id}
                break

    # We get there if no player accepted in the last x minutes
    except asyncio.TimeoutError:
        checkmark_logger.info(
            f"The validation timed out, {' '.join(str(i) for i in ids_of_players_who_validated)} validated"
        )

        result, ids_to_drop = (
            None,
            set(i for i in validating_players_ids if i not in ids_of_players_who_validated),
        )

    checkmark_logger.info(f"Unmarking message {message.id} as queue related")
    queue_channel_handler.unmark_queue_related_message(message)

    return result, ids_to_drop
