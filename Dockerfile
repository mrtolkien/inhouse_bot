FROM python:latest

RUN pip install pipenv

# We base our dependencies on the Pipfile in the repository
COPY Pipfile .
COPY Pipfile.lock .
RUN pipenv install --system --deploy

COPY /inhouse_bot/ /inhouse_bot/
COPY run_bot.py .
CMD ["python", "run_bot.py"]
