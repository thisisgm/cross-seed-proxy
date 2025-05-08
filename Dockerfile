FROM python:3.11-slim

WORKDIR /app

COPY webhook_proxy.py .

RUN pip install --no-cache-dir flask requests gunicorn

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "webhook_proxy:app"]
