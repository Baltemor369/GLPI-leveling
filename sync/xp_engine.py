"""
Calcul XP — Annexes A et B.

XP Technicien (résolution) :
  base_catégorie × coeff_urgence × coeff_impact × coeff_difficulté × coeff_rapidité

XP Créateur (conformité ticket à la création) :
  base_catégorie × (1 + score_conformité / 10)
"""

from datetime import datetime

# ── Annexe A : XP de base par nom de catégorie ────────────────────────────
# Clé = fragment du nom GLPI (insensible à la casse)
_XP_CATEGORIES = [
    ("serveur",        5),
    ("poste client",   3),
    ("poste",          3),
    ("wifi",           2),
    ("wi-fi",          2),
    ("périphérique",   2),
    ("peripherique",   2),
]
XP_CATEGORIE_DEFAUT = 2


def _xp_base(nom_categorie: str) -> int:
    """Retourne l'XP de base selon le nom de catégorie GLPI."""
    nom = (nom_categorie or "").lower().strip()
    for fragment, valeur in _XP_CATEGORIES:
        if fragment in nom:
            return valeur
    return XP_CATEGORIE_DEFAUT


def _coeff_urgence(urgence: int) -> float:
    """×1.2 si urgence haute (≥4), sinon ×1.0."""
    return 1.2 if urgence >= 4 else 1.0


def _coeff_impact(impact: int) -> float:
    """×1.2 si impact haut (≥4), sinon ×1.0."""
    return 1.2 if impact >= 4 else 1.0


def _coeff_difficulte(score: int) -> float:
    """score LLM 1-10 → coefficient 1.1 à 2.0."""
    return 1.0 + max(1, min(10, score)) / 10.0


def _coeff_rapidite(date_creation: str, date_cloture: str) -> float:
    """
    1.5 le jour même, -0.1 par jour, plancher à 1.0 (atteint après 5 jours).
    Accepte ISO 8601 : "2026-06-16T06:45:15+00:00"
    """
    try:
        d_open  = datetime.fromisoformat(date_creation)
        d_close = datetime.fromisoformat(date_cloture)
        jours   = max(0, (d_close - d_open).days)
        return max(1.0, 1.5 - 0.1 * jours)
    except Exception:
        return 1.0


# ── API publique ──────────────────────────────────────────────────────────

def calculer_xp_resolution(
    nom_categorie: str,
    urgence: int,
    impact: int,
    score_difficulte: int,
    date_creation: str,
    date_cloture: str,
) -> int:
    """XP attribué au technicien qui résout le ticket."""
    base = _xp_base(nom_categorie)
    xp   = (base
            * _coeff_urgence(urgence)
            * _coeff_impact(impact)
            * _coeff_difficulte(score_difficulte)
            * _coeff_rapidite(date_creation, date_cloture))
    return max(1, round(xp))


def calculer_xp_conformite(nom_categorie: str, score_conformite: int) -> int:
    """XP attribué au technicien qui a créé le ticket (qualité de saisie)."""
    base = _xp_base(nom_categorie)
    xp   = base * (1.0 + max(1, min(10, score_conformite)) / 10.0)
    return max(1, round(xp))
