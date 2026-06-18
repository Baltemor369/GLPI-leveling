# -*- coding: utf-8 -*-
"""Page principale : Profil de l'aventurier."""

import html
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../sync"))

import db_queries as db
import style
from db import xp_requis_pour_niveau
from auth import require_login, render_sidebar
from version import VERSION

st.set_page_config(
    page_title="GlpiLeveling",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)
style.inject(st)

joueur_id = require_login(main_page=True)
render_sidebar()

# ── Données ────────────────────────────────────────────────────────────────
joueur = db.get_joueur(joueur_id)
equipements = db.get_equipements(joueur_id)

xp_actuel   = joueur["xp"]
niveau       = joueur["level"]
xp_prochain  = xp_requis_pour_niveau(niveau + 1)
xp_precedent = xp_requis_pour_niveau(niveau)
xp_dans_niv  = xp_actuel - xp_precedent
xp_nec       = max(1, xp_prochain - xp_precedent)
pct          = min(100, int(xp_dans_niv / xp_nec * 100))

# ── En-tête joueur ─────────────────────────────────────────────────────────
col_titre, col_or = st.columns([4, 1])
with col_titre:
    st.markdown(f"# ⚔️ {joueur['username'].upper()}")
    st.markdown(f"### Niveau {niveau} &nbsp;·&nbsp; Aventurier")

with col_or:
    st.markdown(f"""
    <div class="stat-card" style="margin-top:12px">
        <div class="stat-label">&#x1F4B0; OR</div>
        <div class="stat-value">{joueur['or_monnaie']}</div>
    </div>
    """, unsafe_allow_html=True)

# Barre XP
st.markdown(f"""
<div class="xp-bar-bg">
    <div class="xp-bar-fill" style="width:{pct}%"></div>
</div>
<div class="xp-label">{xp_actuel} / {xp_prochain} XP &nbsp;&nbsp;({pct}%)</div>
""", unsafe_allow_html=True)

st.markdown("<div class='ornement'>&#9670;&#9670;&#9670;</div>", unsafe_allow_html=True)

# ── Statistiques ───────────────────────────────────────────────────────────
st.markdown("### &#x1F4CA; Statistiques")

if joueur["points_a_attribuer"] > 0:
    st.info(f"✨ {joueur['points_a_attribuer']} point(s) de statistique disponible(s) — répartis-les ci-dessous !")

STATS = [
    ("force_p",         "&#x2694;&#xFE0F; FORCE",         "Dégâts en combat"),
    ("constitution_pv", "&#x1F6E1;&#xFE0F; CONSTITUTION",  "Points de vie max"),
    ("agilite_vit",     "&#x1F4A8; AGILITÉ",               "Initiative & esquive"),
    ("esprit_res",      "&#x1F52E; ESPRIT",                "Résistance aux dégâts"),
]

cols = st.columns(4)
for col, (key, label, desc) in zip(cols, STATS):
    with col:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">{label}</div>
            <div class="stat-value">{joueur[key]}</div>
            <div class="stat-desc">{desc}</div>
        </div>
        """, unsafe_allow_html=True)
        if joueur["points_a_attribuer"] > 0:
            if st.button("+ 1", key=f"stat_{key}"):
                db.depenser_point_stat(joueur_id, key)
                st.rerun()

st.markdown("<div class='ornement'>&#9670;&#9670;&#9670;</div>", unsafe_allow_html=True)

# ── Équipement actif ───────────────────────────────────────────────────────
st.markdown("### &#x1F5E1;&#xFE0F; Équipement")

equipes     = [e for e in equipements if e["equipe"]]
SLOTS       = [("arme","&#x2694;&#xFE0F; ARME"), ("armure","&#x1F6E1;&#xFE0F; ARMURE"), ("amul","&#x1F4FF; AMULETTE")]
STAT_LABELS = {"force_p":"Force","esprit_res":"Résistance","constitution_pv":"PV","agilite_vit":"Agilité"}

cols = st.columns(3)
for col, (type_slot, label) in zip(cols, SLOTS):
    with col:
        item = next((e for e in equipes if e["type"] == type_slot), None)
        if item:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-label">{label}</div>
                <div class="stat-value" style="font-size:1.1rem;margin:8px 0">{item['nom']}</div>
                <div style="color:var(--or);font-size:0.9rem">+{item['valeur_bonus']} {STAT_LABELS.get(item['bonus_stat'],item['bonus_stat'])}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="stat-card" style="opacity:0.35">
                <div class="stat-label">{label}</div>
                <div class="stat-value" style="font-size:1.1rem;margin:8px 0">— Vide —</div>
                <div style="font-size:0.75rem;color:var(--gris)">Forge un équipement</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("<div class='ornement'>&#9670;&#9670;&#9670;</div>", unsafe_allow_html=True)

# ── Derniers tickets ────────────────────────────────────────────────────────
st.markdown("### &#x1F4DC; Derniers tickets traités")
tickets = db.get_tickets_joueur(joueur_id, limit=5)
if not tickets:
    st.markdown("<p style='color:var(--gris);font-style:italic'>Aucun ticket traité pour l'instant.</p>", unsafe_allow_html=True)
else:
    for t in tickets:
        badge   = '<span class="badge-conforme">CONFORME</span>' if t["conforme"] else '<span class="badge-nonconforme">NON CONFORME</span>'
        analyse = html.escape(t["analyse_llm"] or "")
        st.markdown(f"""
        <div class="ticket-row">
            <strong style="color:var(--or-clair)">Ticket #{t['ticket_id']}</strong>
            &nbsp; {badge} &nbsp;
            <span style="color:var(--or)">+{t['xp_gagne']} XP</span>
            <br><small style="color:var(--gris)">{analyse}</small>
        </div>
        """, unsafe_allow_html=True)

st.markdown(
    f"<div style='text-align:right;color:var(--gris);font-size:0.7rem;margin-top:32px'>v{VERSION}</div>",
    unsafe_allow_html=True,
)
