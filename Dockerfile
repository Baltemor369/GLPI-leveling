FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Patch le template HTML statique de Streamlit :
# - fond sombre permanent (élimine le flash blanc inter-pages)
# - overlay JS thématisé (masque la transition pendant le chargement)
COPY patch_streamlit.py .
RUN python patch_streamlit.py && rm patch_streamlit.py

COPY sync/ ./sync/
COPY app/  ./app/

ENV PYTHONPATH=/app/sync:/app/app
ENV PYTHONIOENCODING=utf-8

EXPOSE 8501
