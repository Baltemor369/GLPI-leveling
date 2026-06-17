# -*- coding: utf-8 -*-
"""Page Expédition — 2h en temps réel, loot aléatoire."""

import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sync"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app"))

import streamlit as st
from datetime import timezone
import style
from auth import require_login, render_sidebar
from db import get_conn, get_expedition_active, lancer_expedition, marquer_reclamee, \
               ajouter_materiau, get_materiaux

st.set_page_config(page_title="Expédition — GlpiLeveling", page_icon="🗺️", layout="wide")
style.inject(st)
joueur_id = require_login()
render_sidebar()

DUREE_HEURES = 2

LOOT_TABLE = [
    {"code": "or",              "nom": "Or",              "icone": "🪙", "min": 5,  "max": 15, "chance": 0.70},
    {"code": "bois_chene",      "nom": "Bois de Chêne",   "icone": "🪵", "min": 2,  "max": 4,  "chance": 0.55},
    {"code": "minerai_fer",     "nom": "Minerai de Fer",  "icone": "⚙️", "min": 1,  "max": 3,  "chance": 0.40},
    {"code": "cristal_runique", "nom": "Cristal Runique", "icone": "💎", "min": 1,  "max": 2,  "chance": 0.20},
    {"code": "essence_neant",   "nom": "Essence du Néant","icone": "✨", "min": 1,  "max": 1,  "chance": 0.08},
]

MATERIAU_INFO = {l["code"]: l for l in LOOT_TABLE}


def rouler_loot() -> list[dict]:
    """Tire le loot aléatoirement selon les chances de la table."""
    butin = []
    for item in LOOT_TABLE:
        if random.random() < item["chance"]:
            qty = random.randint(item["min"], item["max"])
            butin.append({"code": item["code"], "nom": item["nom"],
                          "icone": item["icone"], "quantite": qty})
    return butin


def afficher_materiaux(stock: dict):
    cols = st.columns(5)
    for col, loot in zip(cols, LOOT_TABLE):
        with col:
            qty = stock.get(loot["code"], 0)
            st.markdown(f"""
            <div class="stat-card" style="text-align:center">
                <div style="font-size:1.5rem">{loot['icone']}</div>
                <div style="color:var(--gris);font-size:0.75rem;margin:4px 0">{loot['nom']}</div>
                <div style="color:var(--or);font-size:1.1rem"><strong>{qty}</strong></div>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
st.markdown("# 🗺️ Expédition")
st.markdown("*Pars en mission pour rapporter matériaux et richesses. Durée : 2 heures.*")
st.markdown("---")

# ── Inventaire matériaux ──────────────────────────────────────────────────────
conn  = get_conn()
stock = get_materiaux(conn, joueur_id)
conn.close()

st.markdown("### 🎒 Vos matériaux")
afficher_materiaux(stock)
st.markdown("---")

# ── Table de loot ─────────────────────────────────────────────────────────────
with st.expander("📋 Table de loot (ce que vous pouvez trouver)"):
    cols = st.columns(5)
    for col, item in zip(cols, LOOT_TABLE):
        with col:
            st.markdown(f"""
            <div class="stat-card" style="text-align:center">
                <div style="font-size:1.4rem">{item['icone']}</div>
                <div style="color:var(--parchemin);font-size:0.8rem;margin:4px 0">{item['nom']}</div>
                <div style="color:var(--gris);font-size:0.75rem">{item['min']}–{item['max']} unités</div>
                <div style="color:var(--or);font-size:0.85rem">{int(item['chance']*100)}% de chance</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("---")

# ── Résultat d'une réclamation (stocké en session) ───────────────────────────
if "butin_reclame" in st.session_state:
    butin = st.session_state.pop("butin_reclame")
    st.success("🎉 Expédition terminée ! Voici votre butin :")
    if butin:
        cols = st.columns(len(butin))
        for col, item in zip(cols, butin):
            with col:
                st.markdown(f"""
                <div class="stat-card" style="text-align:center;border:1px solid var(--or)">
                    <div style="font-size:2rem">{item['icone']}</div>
                    <div style="color:var(--parchemin)">{item['nom']}</div>
                    <div style="color:var(--or);font-size:1.2rem"><strong>+{item['quantite']}</strong></div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.warning("Votre équipe est revenue bredouille cette fois...")
    st.balloons()
    st.markdown("---")

# ── Statut expédition ─────────────────────────────────────────────────────────
@st.fragment(run_every=30)
def bloc_expedition():
    conn = get_conn()
    expedition = get_expedition_active(conn, joueur_id)
    conn.close()

    if expedition is None:
        st.markdown("### Aucune expédition en cours")
        if st.button("🗺️ Partir en expédition (2h)", use_container_width=True):
            conn = get_conn()
            lancer_expedition(conn, joueur_id, DUREE_HEURES)
            conn.close()
            st.success("Expédition lancée ! Revenez dans 2 heures.")
            st.rerun()
        return

    from datetime import datetime
    now = datetime.now(timezone.utc)
    fin = expedition["fin"]
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=timezone.utc)

    if now >= fin:
        # Expédition terminée — bouton réclamer
        st.markdown("### ✅ Expédition terminée !")
        st.markdown("Votre équipe est de retour. Réclamez votre butin !")
        if st.button("🎁 Réclamer les récompenses", use_container_width=True):
            butin = rouler_loot()
            conn = get_conn()
            marquer_reclamee(conn, expedition["id"])
            for item in butin:
                if item["code"] == "or":
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE joueurs SET or_monnaie = or_monnaie + %s WHERE id = %s",
                            (item["quantite"], joueur_id)
                        )
                    conn.commit()
                else:
                    ajouter_materiau(conn, joueur_id, item["code"], item["quantite"])
            conn.close()
            st.session_state["butin_reclame"] = butin
            st.rerun(scope="app")
    else:
        # En cours — afficher countdown
        reste = fin - now
        heures   = int(reste.total_seconds() // 3600)
        minutes  = int((reste.total_seconds() % 3600) // 60)
        secondes = int(reste.total_seconds() % 60)

        pct = max(0, 1 - reste.total_seconds() / (DUREE_HEURES * 3600))
        st.markdown(f"### ⏳ Expédition en cours — {heures:02d}:{minutes:02d}:{secondes:02d} restant")
        st.markdown(f"""
        <div style="background:#1a0d00;border:1px solid #333;border-radius:6px;height:20px;margin:8px 0">
            <div style="background:var(--or);width:{pct*100:.1f}%;height:100%;border-radius:6px;
                        transition:width 1s"></div>
        </div>
        <div style="color:var(--gris);font-size:0.8rem">
            Retour prévu : {fin.strftime('%H:%M')}
        </div>
        """, unsafe_allow_html=True)

bloc_expedition()
