# -*- coding: utf-8 -*-
"""Page Badges — succès débloqués et à venir."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sync"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app"))

import streamlit as st
import style
from auth import require_login, render_sidebar
from db import get_conn, get_badges_joueur

st.set_page_config(page_title="Badges — GlpiLeveling", page_icon="🏅", layout="wide")
style.inject(st)
joueur_id = require_login()
render_sidebar()

st.markdown("# 🏅 Badges & Succès")
st.markdown("*Accomplis des exploits pour débloquer des badges.*")
st.markdown("---")

conn = get_conn()
badges = get_badges_joueur(conn, joueur_id)
conn.close()

debloque  = [b for b in badges if b["date_obtenu"] is not None]
verrouille = [b for b in badges if b["date_obtenu"] is None]

st.markdown(f"### {len(debloque)} / {len(badges)} badges obtenus")
st.markdown("---")

if debloque:
    st.markdown("### ✅ Débloqués")
    cols = st.columns(4)
    for i, b in enumerate(debloque):
        with cols[i % 4]:
            date_str = b["date_obtenu"].strftime("%d/%m/%Y") if b["date_obtenu"] else ""
            st.markdown(f"""
            <div class="stat-card" style="text-align:center;border:1px solid var(--or)">
                <div style="font-size:2rem">{b['icone']}</div>
                <div class="stat-label" style="color:var(--or);margin:6px 0">{b['nom']}</div>
                <div style="color:var(--gris);font-size:0.75rem">{b['description']}</div>
                <div style="color:var(--gris);font-size:0.7rem;margin-top:6px">Obtenu le {date_str}</div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("---")

if verrouille:
    st.markdown("### 🔒 Verrouillés")
    cols = st.columns(4)
    for i, b in enumerate(verrouille):
        with cols[i % 4]:
            st.markdown(f"""
            <div class="stat-card" style="text-align:center;opacity:0.45">
                <div style="font-size:2rem">🔒</div>
                <div class="stat-label" style="margin:6px 0">{b['nom']}</div>
                <div style="color:var(--gris);font-size:0.75rem">{b['description']}</div>
            </div>
            """, unsafe_allow_html=True)
