# -*- coding: utf-8 -*-
"""Page de visualisation du tableau XP — Annexes A & B."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sync"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app"))

import streamlit as st
import style
from auth import require_login, render_sidebar
from xp_engine import calculer_xp_resolution, calculer_xp_conformite
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Tableau XP — GlpiLeveling", page_icon="📊", layout="wide")
style.inject(st)
require_login()
render_sidebar()

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)

CATEGORIES  = ["Peripherique", "WiFi", "Poste client", "Serveur"]
URGENCES    = [(3, "Normale"), (4, "Haute")]
IMPACTS     = [(3, "Normal"),  (4, "Haut")]
DIFFICULTES = [(2, "Facile"), (5, "Moyen"), (8, "Difficile"), (10, "Expert")]
JOURS       = [(0, "Jour même"), (2, "2 jours"), (5, "5j+ (plancher)")]

st.markdown("# 📊 Tableau des gains XP")
st.markdown("*Visualisation des formules Annexes A & B — utilise les filtres pour explorer.*")
st.markdown("---")

# ── Filtres ────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    filtre_cat = st.multiselect("Catégorie", CATEGORIES, default=CATEGORIES)
with col2:
    filtre_urg = st.multiselect("Urgence", ["Normale", "Haute"], default=["Normale", "Haute"])
with col3:
    filtre_imp = st.multiselect("Impact", ["Normal", "Haut"], default=["Normal", "Haut"])

st.markdown("---")

# ── Tableau XP résolution ──────────────────────────────────────────────────
st.markdown("### ⚔️ XP Résolution — Technicien assigné")

rows = []
for cat in CATEGORIES:
    if cat not in filtre_cat:
        continue
    for urg_val, urg_nom in URGENCES:
        if urg_nom not in filtre_urg:
            continue
        for imp_val, imp_nom in IMPACTS:
            if imp_nom not in filtre_imp:
                continue
            for diff_score, diff_nom in DIFFICULTES:
                for jours, rap_nom in JOURS:
                    d_open  = BASE.isoformat()
                    d_close = (BASE + timedelta(days=jours)).isoformat()
                    xp = calculer_xp_resolution(cat, urg_val, imp_val, diff_score, d_open, d_close)
                    rows.append({
                        "Catégorie":  cat,
                        "Urgence":    urg_nom,
                        "Impact":     imp_nom,
                        "Difficulté": diff_nom,
                        "Rapidité":   rap_nom,
                        "XP":         xp,
                    })

import pandas as pd
df = pd.DataFrame(rows)

# Colorer les XP
def color_xp(val):
    if val <= 5:   return "background-color:#2c1810;color:#7a6a55"
    if val <= 12:  return "background-color:#2c2010;color:#c9a84c"
    if val <= 25:  return "background-color:#1a2010;color:#8fbf8f"
    return "background-color:#101828;color:#6ab0e8"

st.dataframe(
    df.style.map(color_xp, subset=["XP"]),
    use_container_width=True,
    height=500,
)

xp_min = df["XP"].min()
xp_max = df["XP"].max()
xp_moy = df["XP"].mean()
c1, c2, c3 = st.columns(3)
c1.metric("XP minimum", xp_min)
c2.metric("XP maximum", xp_max)
c3.metric("XP moyen", f"{xp_moy:.1f}")

st.markdown("---")

# ── Tableau XP conformité ──────────────────────────────────────────────────
st.markdown("### 📝 XP Conformité — Technicien créateur du ticket")

rows2 = []
for cat in CATEGORIES:
    if cat not in filtre_cat:
        continue
    for score in range(1, 11):
        xp = calculer_xp_conformite(cat, score)
        rows2.append({
            "Catégorie":        cat,
            "Score conformité": f"{score}/10",
            "Score (num)":      score,
            "XP":               xp,
        })

df2 = pd.DataFrame(rows2)
st.dataframe(
    df2.drop(columns=["Score (num)"]).style.map(color_xp, subset=["XP"]),
    use_container_width=True,
    height=300,
)

st.markdown("---")
st.markdown("""
<div style='color:var(--gris);font-size:0.85rem'>
<strong>Légende couleurs XP :</strong>
&nbsp; <span style='background:#2c1810;color:#7a6a55;padding:2px 8px;border-radius:3px'>≤ 5 (faible)</span>
&nbsp; <span style='background:#2c2010;color:#c9a84c;padding:2px 8px;border-radius:3px'>6-12 (normal)</span>
&nbsp; <span style='background:#1a2010;color:#8fbf8f;padding:2px 8px;border-radius:3px'>13-25 (élevé)</span>
&nbsp; <span style='background:#101828;color:#6ab0e8;padding:2px 8px;border-radius:3px'>26+ (exceptionnel)</span>
</div>
""", unsafe_allow_html=True)
