FROM python:3.11-slim

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sync/ ./sync/
COPY web/  ./web/

RUN chown -R app:app /app

USER app

ENV PYTHONPATH=/app/sync:/app
ENV PYTHONIOENCODING=utf-8

EXPOSE 8501
