FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY bot.py database.py movie_search.py .

CMD ["python", "bot.py"]