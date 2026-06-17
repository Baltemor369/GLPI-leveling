"""Affiche le tableau complet des gains XP pour validation."""
import sys
sys.path.insert(0, "F:/0_Dev/GLPI-leveling/sync")

from datetime import datetime, timedelta, timezone
from xp_engine import calculer_xp_resolution, calculer_xp_conformite

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)

CATEGORIES  = ["Peripherique", "WiFi", "Poste client", "Serveur"]
URGENCES    = [(3, "Normale"), (4, "Haute")]
IMPACTS     = [(3, "Normal"),  (4, "Haut")]
DIFFICULTES = [(2, "Facile"), (5, "Moyen"), (8, "Difficile"), (10, "Expert")]
JOURS       = [(0, "Jour meme"), (2, "2 jours"), (5, "5j+ (plancher)")]

# ── Tableau XP résolution ─────────────────────────────────────────────────
print("=" * 92)
print(f"{'Categorie':<14} {'Urgence':<9} {'Impact':<8} {'Difficulte':<12} {'Rapidite':<16} {'XP':>6}")
print("=" * 92)

for cat in CATEGORIES:
    for urg_val, urg_nom in URGENCES:
        for imp_val, imp_nom in IMPACTS:
            for diff_score, diff_nom in DIFFICULTES:
                for jours, rap_nom in JOURS:
                    d_open  = BASE.isoformat()
                    d_close = (BASE + timedelta(days=jours)).isoformat()
                    xp = calculer_xp_resolution(cat, urg_val, imp_val, diff_score, d_open, d_close)
                    print(f"{cat:<14} {urg_nom:<9} {imp_nom:<8} {diff_nom:<12} {rap_nom:<16} {xp:>6}")
    print("-" * 92)

# ── Tableau XP conformité ─────────────────────────────────────────────────
print()
print("=" * 48)
print(f"{'Categorie':<14} {'Score conformite':<22} {'XP':>6}")
print("=" * 48)

for cat in CATEGORIES:
    for score in [1, 3, 5, 7, 9, 10]:
        xp = calculer_xp_conformite(cat, score)
        label = str(score) + "/10"
        print(f"{cat:<14} {label:<22} {xp:>6}")
    print("-" * 48)
