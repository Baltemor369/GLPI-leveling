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

require_login()
render_sidebar()

st.markdown("# &#x1F3C6; Classement des Aventuriers")
st.markdown("---")

joueurs = db.tous_les_joueurs()
if not joueurs:
    st.warning("Aucun joueur en base.")
    st.stop()

MEDAILLES = {1: "🥇", 2: "🥈", 3: "🥉"}

for rang, j in enumerate(joueurs, start=1):
    medaille = MEDAILLES.get(rang, f"#{rang}")
    css_rang = f"rank-{rang}" if rang <= 3 else ""
    username_safe = html.escape(j["username"])

    col1, col2, col3, col4, col5 = st.columns([0.5, 2.5, 1, 1.5, 2])
    with col1:
        st.markdown(f"<div style='font-size:1.5rem;text-align:center'>{medaille}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<span class='{css_rang}' style='font-size:1.1rem'>{username_safe}</span>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"**Niv. {j['level']}**")
    with col4:
        st.markdown(f"<span style='color:#c9a84c'>⭐ {j['xp']} XP</span>", unsafe_allow_html=True)
    with col5:
        xp_prec = xp_requis_pour_niveau(j["level"])
        xp_suiv = xp_requis_pour_niveau(j["level"] + 1)
        pct = min(100, int((j["xp"] - xp_prec) / max(1, xp_suiv - xp_prec) * 100))
        st.markdown(f"""
        <div class="xp-bar-bg" style="height:14px;margin-top:6px">
            <div class="xp-bar-fill" style="width:{pct}%"></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#3d2314;margin:6px 0'>", unsafe_allow_html=True)
