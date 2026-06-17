"""
Analyse LLM (Ollama) — un seul appel par ticket, deux scores retournés :
  score_conformite  (1-10) : qualité de saisie du ticket (Annexe B)
  score_difficulte  (1-10) : complexité technique du problème résolu (Annexe A)
"""

import json
import re

import requests

from config import OLLAMA_API_URL, OLLAMA_MODEL

# ── Annexe B : critères de conformité ─────────────────────────────────────
_CRITERES_CONFORMITE = """
1. TITRE : contient le nom ET le prénom de l'appelant + son problème/demande
   (ex: "Marie Dupont - plus de connexion wifi")
2. DESCRIPTION : contient un moyen de contact — numéro de téléphone et/ou adresse e-mail
   (ex: "06 12 34 56 78" ou "marie.dupont@example.com")
3. CLARTÉ GLOBALE : les deux champs sont lisibles, précis et complets
   (un score faible si le texte est vague, trop court ou incompréhensible)
"""

_PROMPT = """Tu es un vérificateur qualité de tickets helpdesk pour un service informatique.
Tu reçois le TITRE, la DESCRIPTION et la SOLUTION d'un ticket.
Tu dois retourner deux scores entiers entre 1 et 10.

=== SCORE CONFORMITÉ (qualité de saisie) ===
Critères obligatoires :
{criteres}
Barème :
- 1-3 : informations manquantes ou incompréhensibles
- 4-6 : informations partielles ou imprécises
- 7-9 : informations présentes mais perfectibles
- 10  : ticket parfaitement rempli, tout est clair et complet

=== SCORE DIFFICULTÉ (complexité technique) ===
Évalue la complexité du problème et la qualité de la résolution :
- 1-3 : problème simple, solution évidente (redémarrage, câble débranché...)
- 4-6 : problème intermédiaire, nécessite une investigation
- 7-9 : problème complexe, compétences techniques avancées requises
- 10  : incident critique ou résolution exceptionnelle

Réponds UNIQUEMENT avec un objet JSON valide :
{{"score_conformite": <entier 1-10>, "explication_conformite": "<courte>",
  "score_difficulte": <entier 1-10>, "explication_difficulte": "<courte>"}}

=== TICKET À ANALYSER ===
TITRE      : {titre}
DESCRIPTION: {description}
SOLUTION   : {solution}

JSON :"""


def analyser_ticket(titre: str, description: str, solution: str) -> dict:
    """
    Appel unique au LLM — retourne :
      {
        "score_conformite": int,      # 1-10
        "explication_conformite": str,
        "score_difficulte": int,      # 1-10
        "explication_difficulte": str,
      }
    En cas d'erreur, renvoie des scores par défaut (5/5).
    """
    prompt = _PROMPT.format(
        criteres    = _CRITERES_CONFORMITE,
        titre       = titre       or "(vide)",
        description = description or "(vide)",
        solution    = solution    or "(vide)",
    )

    try:
        resp = requests.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=120,
        )
        resp.raise_for_status()
        raw = resp.json()["response"].strip()

        # Extraire le JSON même si le LLM ajoute du texte autour
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data  = json.loads(match.group() if match else raw)

        return {
            "score_conformite":       int(data.get("score_conformite", 5)),
            "explication_conformite": str(data.get("explication_conformite", "")),
            "score_difficulte":       int(data.get("score_difficulte", 5)),
            "explication_difficulte": str(data.get("explication_difficulte", "")),
        }
    except Exception as e:
        print(f"  [LLM] Erreur analyse ticket : {e}")
        return {
            "score_conformite": 5,
            "explication_conformite": "Analyse indisponible.",
            "score_difficulte": 5,
            "explication_difficulte": "Analyse indisponible.",
        }
