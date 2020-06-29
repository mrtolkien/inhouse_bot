FROM python:latest

RUN pip install pipenv

# We base our dependencies on the Pipfile in the repository
COPY Pipfile* /tmp/
RUN cd /tmp && pipenv lock --requirements > requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY /inhouse_bot/ /inhouse_bot/
COPY run_bot.py .
CMD ["python", "run_bot.py"]
