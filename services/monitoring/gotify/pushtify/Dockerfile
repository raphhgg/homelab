FROM python:3.12-alpine
RUN pip install --no-cache-dir websocket-client requests
COPY pushtify-listener.py /usr/local/bin/
ENTRYPOINT ["python3", "-u", "/usr/local/bin/pushtify-listener.py"]
