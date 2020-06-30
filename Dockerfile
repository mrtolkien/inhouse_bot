FROM python:latest

# pipenv install
WORKDIR /pipenv
COPY Pipfile* /pipenv/
# Workaround due to recent pipenv versions having issues with Docker
RUN pip install 'pipenv==2018.11.26'
RUN pipenv install --deploy --system

WORKDIR /
COPY /inhouse_bot/ /inhouse_bot/
COPY run_bot.py .
CMD ["python", "run_bot.py"]
