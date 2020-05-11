# LoL in-house bot
A Discord bot to handle League of Legends in-house games, with role queue, balanced matchmaking, and basic stats.

# Basic use
```
# Enter the channel’s matchamking queue
!queue mid
>>> 🇲

# Accept queue by reacting to the ready check message

# Games can be scored with !won and !lost, and you can optionally inform the champion you used
!won riven
>>> Game 1 has been scored as a win for blue and ratings have been updated.

!rating
>>> Your rating for top is 2.6 over 1 game
```

# Use case and behaviour

This bot is made to be used by trustworthy players queuing regularly for one or two roles.

There is one queue per discord channel the bot is in, but player ratings are common to all channels.

Players can queue in multiple channels and multiple roles. A game starting will drop them from 
all queues in all channels. A player can’t re-enter a queue as long as any game they’re in has not been scored or 
cancelled.

Each player’s role rating is treated as an independent entity, and they all start from the same rating.
The rating system is based on [Microsoft TrueSkill](https://en.wikipedia.org/wiki/TrueSkill).

# Queue features
`!queue role` puts you in the current channel’s queue for the given role.

`!leave` removes you from the channel’s queue for all roles.

`!leave all` removes you from all channel’s queue for all roles.

`!won [champion_name]` scores your last game as a win for your team, and you can optionally inform which champion you 
used for winrate tracking.

`!lost [champion_name]` is the counterpart to `!won`. If there is a conflict in the last game’s result, the bot will
ask for validation.

`!view_queue` shows the queue in the current channel.

`!view_games` shows the ongoing games for all channels.

`!cancel_game` cancels your ongoing game, requiring validation from at least 6 players in the game.

# Stats features
`!rank` returns your server-wide rank.

`!mmr` returns your current MMR.

`!mmr_history` displays a graph of your MMR per role in the past month.

# Installation
```shell script
git clone https://github.com/mrtolkien/inhouse_bot.git
cd inhouse_bot
pipenv install
pipenv run python run_bot.py
```

# Wanted contributions (2020-05-11)
- `dpytest` doesn’t mock adding reactions to messages, which means the test functions are currently failing.
Any help with mocking those would be greatly welcomed.

- The matchmaking algorithm is currently fully brute-force and can definitely be improved in terms of calculation time.

- Additions to stats visualisations are always welcomed!
