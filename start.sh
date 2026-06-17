#!/bin/bash
# Script de premier démarrage — GlpiLeveling
# Usage : bash start.sh

set -e

if [ ! -f .env ]; then
  echo "[!] Fichier .env manquant. Copier .env.example et le remplir :"
  echo "    cp .env.example .env && nano .env"
  exit 1
fi

echo "[1/3] Démarrage de la base de données et d'Ollama..."
docker compose up -d db ollama

echo "[2/3] Téléchargement du modèle LLM (première fois uniquement, peut prendre quelques minutes)..."
# Attendre qu'Ollama soit prêt
until docker compose exec ollama curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
  echo "      En attente d'Ollama..."
  sleep 3
done
OLLAMA_MODEL=$(grep OLLAMA_MODEL .env | cut -d= -f2 | tr -d ' ')
docker compose exec ollama ollama pull "${OLLAMA_MODEL:-mistral}"

echo "[3/3] Démarrage de l'application et du worker..."
docker compose up -d app worker

echo ""
echo "GlpiLeveling est prêt !"
PORT=$(grep APP_PORT .env | cut -d= -f2 | tr -d ' ')
echo "Accès : http://$(hostname -I | awk '{print $1}'):${PORT:-8501}"
