FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Patch le template HTML de Streamlit pour injecter le fond sombre dès le chargement.
# Sans ça, React retire notre <style> entre deux pages → flash blanc pendant la transition.
RUN python -c "\
import streamlit, os; \
p = os.path.join(os.path.dirname(streamlit.__file__), 'static', 'index.html'); \
css = '<style>html,body,#root{background-color:#2c1810!important;margin:0;padding:0}</style>'; \
c = open(p).read().replace('</head>', css + '</head>', 1); \
open(p, 'w').write(c)"

COPY sync/ ./sync/
COPY app/  ./app/

ENV PYTHONPATH=/app/sync:/app/app
ENV PYTHONIOENCODING=utf-8

EXPOSE 8501
