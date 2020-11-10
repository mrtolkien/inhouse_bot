# Sticking to 3.8 at the moment because some packages don’t have wheels for 3.9 as of November 2020
FROM python:3.8 AS inhouse_bot

# Installing from files for better readability
COPY requirements.txt /
RUN pip install -r /requirements.txt

# I’m using a single image at the moment, so I put pytest in it too
RUN pip install pytest

# Copying the bot source code
WORKDIR /inhouse_bot
COPY /inhouse_bot/ ./inhouse_bot
COPY run_bot.py .

# Running the bot itself
CMD python -u run_bot.py
