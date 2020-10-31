# Sticking to 3.8 at the moment because some packages don’t have wheels for 3.9 as of November 2020
FROM python:3.8 AS inhouse_bot

# Installing from files for better readability
COPY requirements.txt /
RUN pip install -r /requirements.txt

# Copying the bot source code
# TODO CHANGE THAT FOR NEW STUFF
WORKDIR /
COPY /inhouse_bot_old/ /inhouse_bot/
COPY run_bot.py .

# Running the bot itself
CMD python -u run_bot.py


# Small development environment
FROM inhouse_bot as inhouse_bot_dev

RUN pip install pytest
