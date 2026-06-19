# -*- coding: utf-8 -*-
"""Page Expédition — 2h en temps réel, loot pondéré 3 rolls + pity."""

import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sync"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app"))

import streamlit as st
from datetime import timezone
import style
from auth import require_login, render_sidebar
from db import get_conn, get_expedition_active, lancer_expedition, marquer_reclamee, \
               ajouter_materiau, get_materiaux
from badge_engine import verifier_badges_expedition

st.set_page_config(page_title="Expédition — GlpiLeveling", page_icon="🗺️", layout="wide")
style.inject(st)
joueur_id = require_login()
render_sidebar()

DUREE_HEURES = 2
NB_ROLLS     = 3
PITY_SEUIL   = 10

LOOT_TABLE = [
    {"code": "or",              "nom": "Or",               "icone": "💰", "poids": 38, "min": 5,  "max": 15},
    {"code": "bois_chene",      "nom": "Bois de Chêne",    "icone": "🌲", "poids": 28, "min": 2,  "max": 4},
    {"code": "minerai_fer",     "nom": "Minerai de Fer",   "icone": "⚙️", "poids": 20, "min": 1,  "max": 3},
    {"code": "cristal_runique", "nom": "Cristal Runique",  "icone": "💎", "poids": 10, "min": 1,  "max": 2},
    {"code": "essence_neant",   "nom": "Essence du Néant", "icone": "✨", "poids": 4,  "min": 1,  "max": 1},
]
_POIDS = [item["poids"] for item in LOOT_TABLE]
_ESSENCE = next(i for i in LOOT_TABLE if i["code"] == "essence_neant")


def rouler_loot(pity: int) -> tuple[list[dict], bool]:
    """3 rolls pondérés. Si pity >= PITY_SEUIL, force Essence sur 1 roll."""
    butin_dict = {}
    essence_obtenue = False
    rolls_restants = NB_ROLLS

    if pity >= PITY_SEUIL:
        qty = random.randint(_ESSENCE["min"], _ESSENCE["max"])
        butin_dict["essence_neant"] = qty
        essence_obtenue = True
        rolls_restants -= 1

    for _ in range(rolls_restants):
        item = random.choices(LOOT_TABLE, weights=_POIDS, k=1)[0]
        qty  = random.randint(item["min"], item["max"])
        butin_dict[item["code"]] = butin_dict.get(item["code"], 0) + qty
        if item["code"] == "essence_neant":
            essence_obtenue = True

    butin = []
    for code, qty in butin_dict.items():
        info = next(i for i in LOOT_TABLE if i["code"] == code)
        butin.append({"code": code, "nom": info["nom"], "icone": info["icone"], "quantite": qty})
    return butin, essence_obtenue


def get_pity(conn, jid: int) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT pity_expedition FROM joueurs WHERE id = %s", (jid,))
        row = cur.fetchone()
        return row[0] if row else 0


def set_pity(conn, jid: int, pity: int):
    with conn.cursor() as cur:
        cur.execute("UPDATE joueurs SET pity_expedition = %s WHERE id = %s", (pity, jid))


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
pity_actuel = get_pity(conn, joueur_id)
with conn.cursor() as _cur:
    _cur.execute("SELECT or_monnaie FROM joueurs WHERE id = %s", (joueur_id,))
    stock["or"] = (_cur.fetchone() or [0])[0]
conn.close()

st.markdown("### 🎒 Vos matériaux")
afficher_materiaux(stock)

if pity_actuel > 0:
    pity_label = f"🔮 Pity Essence : **{pity_actuel}/{PITY_SEUIL}** expéditions sans Essence du Néant"
    if pity_actuel >= PITY_SEUIL:
        st.warning(f"{pity_label} — **Garantie active : prochaine expédition drop Essence !**")
    else:
        st.info(pity_label)

st.markdown("---")

# ── Table de loot ─────────────────────────────────────────────────────────────
total_poids = sum(_POIDS)
with st.expander("📋 Table de loot — probabilités par roll"):
    cols = st.columns(5)
    for col, item in zip(cols, LOOT_TABLE):
        with col:
            pct = item["poids"] / total_poids * 100
            st.markdown(f"""
            <div class="stat-card" style="text-align:center">
                <div style="font-size:1.4rem">{item['icone']}</div>
                <div style="color:var(--parchemin);font-size:0.8rem;margin:4px 0">{item['nom']}</div>
                <div style="color:var(--gris);font-size:0.75rem">{item['min']}–{item['max']} unités</div>
                <div style="color:var(--or);font-size:0.85rem">{pct:.0f}% / roll</div>
            </div>
            """, unsafe_allow_html=True)
    st.caption(f"3 rolls par expédition • Pity Essence garantie à {PITY_SEUIL} expéditions sans en obtenir")

st.markdown("---")

# ── Résultat d'une réclamation (stocké en session) ───────────────────────────
if "butin_reclame" in st.session_state:
    butin = st.session_state.pop("butin_reclame")
    pity_info = st.session_state.pop("pity_info", None)
    nouveaux_badges = st.session_state.pop("nouveaux_badges_exp", [])
    st.success("🎉 Expédition terminée ! Voici votre butin :")
    if pity_info == "garanti":
        st.info("✨ Pity activé — Essence du Néant garantie !")
    if butin:
        cols = st.columns(len(butin))
        for col, item in zip(cols, butin):
            with col:
                border = "1px solid #c9a84c" if item["code"] == "essence_neant" else "1px solid var(--or)"
                st.markdown(f"""
                <div class="stat-card" style="text-align:center;border:{border}">
                    <div style="font-size:2rem">{item['icone']}</div>
                    <div style="color:var(--parchemin)">{item['nom']}</div>
                    <div style="color:var(--or);font-size:1.2rem"><strong>+{item['quantite']}</strong></div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.warning("Votre équipe est revenue bredouille cette fois...")
    st.balloons()
    for code in nouveaux_badges:
        st.success(f"🏅 Badge débloqué : **{code}** !")
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
        st.markdown("### ✅ Expédition terminée !")
        st.markdown("Votre équipe est de retour. Réclamez votre butin !")
        if st.button("🎁 Réclamer les récompenses", use_container_width=True):
            conn = get_conn()
            pity = get_pity(conn, joueur_id)
            butin, essence_obtenue = rouler_loot(pity)
            pity_info = "garanti" if pity >= PITY_SEUIL else None

            if not marquer_reclamee(conn, expedition["id"]):
                conn.rollback()
                conn.close()
                st.warning("Cette expédition a déjà été réclamée.")
                st.rerun()

            for item in butin:
                if item["code"] == "or":
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE joueurs SET or_monnaie = or_monnaie + %s WHERE id = %s",
                            (item["quantite"], joueur_id),
                        )
                else:
                    ajouter_materiau(conn, joueur_id, item["code"], item["quantite"])

            nouveau_pity = 0 if essence_obtenue else pity + 1
            set_pity(conn, joueur_id, nouveau_pity)
            conn.commit()  # Un seul commit : marquer + loot + pity
            nouveaux_badges = verifier_badges_expedition(conn, joueur_id, butin)
            conn.close()

            st.session_state["butin_reclame"] = butin
            st.session_state["nouveaux_badges_exp"] = nouveaux_badges
            if pity_info:
                st.session_state["pity_info"] = pity_info
            st.rerun(scope="app")
    else:
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
            Retour prévu : {fin.astimezone().strftime('%H:%M')}
        </div>
        """, unsafe_allow_html=True)

bloc_expedition()
