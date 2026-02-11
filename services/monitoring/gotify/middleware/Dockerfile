FROM python:3.12-alpine
RUN pip install --no-cache-dir flask requests gunicorn
COPY . /app
WORKDIR /app
ENTRYPOINT ["gunicorn", "-b", "0.0.0.0:5000", "-w", "2", "--access-logfile", "-", "app:app"]
