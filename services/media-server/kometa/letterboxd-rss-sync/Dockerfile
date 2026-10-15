FROM python:3.13-alpine

WORKDIR /app

RUN pip install --no-cache-dir requests PyYAML

COPY sync_recent_ratings.py /app/sync_recent_ratings.py

CMD ["python", "/app/sync_recent_ratings.py"]
