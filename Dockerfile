FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sync/ ./sync/
COPY app/  ./app/

ENV PYTHONPATH=/app/sync:/app/app
ENV PYTHONIOENCODING=utf-8

EXPOSE 8501
