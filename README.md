[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# LoL in-house bot
A Discord bot to handle League of Legends in-house games, with role queue, matchmaking, and rankings.

# Demo
![Demo](.demo.gif)

# Installation

## Video tutorial
[![](http://img.youtube.com/vi/TksVS8PE2fw/0.jpg)](http://www.youtube.com/watch?v=TksVS8PE2fw "Youtube Video")

## Text steps

- Install [Docker](https://docs.docker.com/get-docker/)

    - I wrote an [in-depth tutorial about using Docker here](https://lol-data.com/development/realistic-python-docker-work-flow/)

- Get your Discord bot token from [the Discord developer portal](https://discord.com/developers/applications)

- Activate your bot on the Discord developer portal and give it the Server Members privileged intent

- Invite the bot to your server through OAuth2

- Add emoji for all 5 LoL roles to your server

    - They are handled separately than champion emoji as they’re crucial for the bot to work

    - Optional: invite your bot to servers that have emoji for each champion, for example :TwistedFate: for Twisted Fate and :KaiSa: for Kai’Sa. You can also define a :loading: emoji that will be used by the bot 

- Create a `docker-compose.yml` file based [on this docker compose file](https://github.com/mrtolkien/inhouse_bot/blob/master/docker-compose-example.yml)

- Edit the file to add your Discord bot token as well as the Discord ID of your emojis, and change the database default password to something random

     - You can add the environment variable `INHOUSE_BOT_TEST=1` to the bot’s variables and it will add a few `!test` commands

     - You can add the environment variable `INHOUSE_BOT_COMMAND_PREFIX` to customize the prefix of the bot (will default to `!`).

- Run `docker-compose up -d` and your bot should be up and running!

    - If you also added the `adminer` service, you can use http://localhost:8080/ to manage the database
    
- Use `!admin mark queue` to define queue channels

# Basic use
```
# Enter the channel’s matchmaking queue
!queue mid
>>> 🇲

# Accept games by reacting to the ready check message
>>> ✅✅✅✅✅✅✅✅✅✅✅
>>> Game 1 has started

# Games can be scored with !won
!won
>>> ✅✅✅✅✅✅✅
>>> Game 1 has been scored as a win for blue and ratings have been updated

# Champion played can be added with !champion
!champion riven
>>> Champion for game 1 set to Riven for Tolki

# Your rank, mmr, and # of games can be seen with !rank or !mmr
!rank
>>> Server    Role      Games  Rank      MMR
    --------  ------  -------  ------  -----
    LEA       MID           1  1st    27.09
```

# Rating and matchmaking explanation

Rating:
- Each player has one rating per server and role, and each rating is completely independent
- There is one queue per discord channel the bot is in, but ratings are server-wide
- The ratings are loosely based on [Microsoft TrueSkill](https://en.wikipedia.org/wiki/TrueSkill)
- The displayed MMR is a conservative estimate of skill and starts at 25 for everybody

Matchmaking:
- Players who have been in queue the longest will be favored when creating a game
- Matchmaking aims to select the game with a predicted winrate as close as possible to 50%
- Side assignment is random

# Use case and behaviour

This bot is made to be used by trustworthy players queuing regularly for one or two roles. It will not transfer well to
an uncontrolled environment.

Players can queue in multiple channels and multiple roles. A game starting will drop them from 
all queues in all channels. A player can’t re-enter a queue as long as any game they’re in has not been scored or 
cancelled.

# Queue features
- `!queue role` puts you in the current channel’s queue for the given role

- `!queue role @user other_role` duo queues you together with the tagged player in the current channel

- `!leave` removes you from the channel’s queue for all roles

- `!won` scores your last game as a win for your team and waits for validation from at least 6 players from the game

- `!champion champion_name [game_id]` informs which champion you used for winrate tracking
    - If you don’t supply the `game_id`, it will apply to your last game

- `!cancel` cancels your ongoing game, requiring validation from at least 6 players in the game
 
# Stats features
- `!history` returns your match history

- `!rank` returns your server-wide rank for each role

- `!ranking` returns the top players

# Admin features
- `!admin reset @user` removes the user from all queues (his name or discord ID work too)

- `!admin reset #channel` resets the queue in the given channel (or the current channel with `!admin reset`)

- `!admin won @user` scores the game as a win for the user without asking for validation

- `!admin cancel @user` cancels the ongoing game of the specified user


# Wanted contributions (2020-05-11)
- `dpytest` does not support reactions to messages, which means the test functions are currently failing

- The matchmaking algorithm is currently fully brute-force and can definitely be improved in terms of calculation time

- Additions to stats visualisations are always welcomed!

- Make it more flexible so it can work with other games/games without roles (Valorant, ...)
