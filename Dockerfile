FROM python AS inhouse_bot

# Installing from files for better readability
COPY requirements.txt /
RUN pip install -r /requirements.txt

# I’m using a single image at the moment, so I put pytest in it too
RUN pip install pytest

# Copying the bot source code
WORKDIR /inhouse_bot
COPY /inhouse_bot/ ./inhouse_bot
COPY /tests/ ./tests/
COPY run_bot.py .

# Running the bot itself
CMD python -u run_bot.py
