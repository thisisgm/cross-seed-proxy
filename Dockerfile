
FROM python:3.12-slim

WORKDIR /app
COPY webhook_proxy.py /app

RUN pip install Flask requests

CMD ["python", "webhook_proxy.py"]
