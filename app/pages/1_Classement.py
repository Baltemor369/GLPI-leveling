# -*- coding: utf-8 -*-
"""Page Classement — tableau des scores entre techniciens."""

import html
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sync"))
import db_queries as db
import style
from auth import require_login, render_sidebar
from db import xp_requis_pour_niveau

st.set_page_config(page_title="Classement — GlpiLeveling", page_icon="🏆", layout="wide")
style.inject(st)

joueur_id = require_login()
render_sidebar()

st.markdown("# &#x1F3C6; Classement des Aventuriers")
st.markdown("---")

joueurs = db.tous_les_joueurs()
if not joueurs:
    st.warning("Aucun joueur en base.")
    st.stop()

# Rang du joueur connecté
mon_rang = next((i + 1 for i, j in enumerate(joueurs) if j["id"] == joueur_id), None)
if mon_rang:
    st.markdown(
        f"<div style='text-align:right;color:#c9a84c;font-size:0.85rem;margin-top:-12px;margin-bottom:12px'>"
        f"Votre position : <strong>#{mon_rang}</strong> sur {len(joueurs)} aventuriers</div>",
        unsafe_allow_html=True,
    )

MEDAILLES = {1: "🥇", 2: "🥈", 3: "🥉"}

for rang, j in enumerate(joueurs, start=1):
    est_moi   = j["id"] == joueur_id
    medaille  = MEDAILLES.get(rang, f"#{rang}")
    css_rang  = f"rank-{rang}" if rang <= 3 else ""
    username_safe = html.escape(j["username"])

    me_badge = (
        " <span style='background:#c9a84c;color:#1a0d00;"
        "font-size:0.6rem;padding:1px 5px;border-radius:3px;"
        "font-weight:bold;vertical-align:middle'>VOUS</span>"
        if est_moi else ""
    )
    name_color = "color:#c9a84c;font-weight:bold" if est_moi else ""
    hr_color   = "#c9a84c" if est_moi else "#3d2314"

    col1, col2, col3, col4, col5, col6 = st.columns([0.5, 2.5, 1, 1.5, 1, 1.5])
    with col1:
        st.markdown(
            f"<div style='font-size:1.5rem;text-align:center'>{medaille}</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"<span class='{css_rang}' style='font-size:1.1rem;{name_color}'>"
            f"{username_safe}</span>{me_badge}",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(f"**Niv. {j['level']}**")
    with col4:
        st.markdown(
            f"<span style='color:#c9a84c'>⭐ {j['xp']} XP</span>",
            unsafe_allow_html=True,
        )
    with col5:
        st.markdown(
            f"<span style='color:#e87070'>⚔️ {j['victoires']}</span>",
            unsafe_allow_html=True,
        )
    with col6:
        xp_prec = xp_requis_pour_niveau(j["level"])
        xp_suiv = xp_requis_pour_niveau(j["level"] + 1)
        pct = min(100, int((j["xp"] - xp_prec) / max(1, xp_suiv - xp_prec) * 100))
        st.markdown(
            f"""<div class="xp-bar-bg" style="height:14px;margin-top:6px">
                <div class="xp-bar-fill" style="width:{pct}%"></div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<hr style='border-color:{hr_color};margin:6px 0'>",
        unsafe_allow_html=True,
    )
