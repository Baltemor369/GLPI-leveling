"""Page Forge — achat et équipement d'objets."""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sync"))
import db_queries as db
import style
import psycopg2
from db import get_conn
import badge_engine

from auth import require_login, render_sidebar

st.set_page_config(page_title="Forge — GlpiLeveling", page_icon="🔨", layout="wide")
style.inject(st)

joueur_id = require_login()
render_sidebar()

st.markdown("# &#x1F528; La Forge")
st.markdown("*Dépense ton or pour forger des équipements et renforcer ton aventurier.*")
st.markdown("---")

joueur = db.get_joueur(joueur_id)
if not joueur:
    st.warning("Profil introuvable. Assure-toi d'avoir au moins un ticket assigné.")
    st.stop()

st.markdown(f"**Or disponible : 🪙 {joueur['or_monnaie']}**")
st.markdown("---")

# Catalogue des objets
CATALOGUE = [
    {"nom": "Epée en fer",        "type": "arme",   "bonus_stat": "force_p",       "valeur_bonus": 5,  "cout": 30},
    {"nom": "Epée en acier",      "type": "arme",   "bonus_stat": "force_p",       "valeur_bonus": 12, "cout": 80},
    {"nom": "Hache de guerre",    "type": "arme",   "bonus_stat": "force_p",       "valeur_bonus": 20, "cout": 150},
    {"nom": "Tunique de cuir",    "type": "armure", "bonus_stat": "esprit_res",    "valeur_bonus": 5,  "cout": 25},
    {"nom": "Cotte de mailles",   "type": "armure", "bonus_stat": "esprit_res",    "valeur_bonus": 12, "cout": 70},
    {"nom": "Armure de plates",   "type": "armure", "bonus_stat": "esprit_res",    "valeur_bonus": 22, "cout": 180},
    {"nom": "Amulette de vitalité","type": "amul",  "bonus_stat": "constitution_pv","valeur_bonus": 8, "cout": 40},
    {"nom": "Bague de célérité",  "type": "amul",   "bonus_stat": "agilite_vit",   "valeur_bonus": 6,  "cout": 45},
]

TYPE_LABELS = {"arme": "⚔️ Armes", "armure": "🛡️ Armures", "amul": "📿 Amulettes"}
STAT_LABELS = {
    "force_p": "Force", "esprit_res": "Résistance",
    "constitution_pv": "PV", "agilite_vit": "Agilité",
}

for type_key, type_label in TYPE_LABELS.items():
    st.markdown(f"### {type_label}")
    items = [i for i in CATALOGUE if i["type"] == type_key]
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            peut_acheter = joueur["or_monnaie"] >= item["cout"]
            st.markdown(f"""
            <div class="stat-card" style="{'opacity:0.5' if not peut_acheter else ''}">
                <div class="stat-label">{item['nom']}</div>
                <div class="stat-value" style="font-size:1rem">+{item['valeur_bonus']} {STAT_LABELS[item['bonus_stat']]}</div>
                <div style="color:#c9a84c;margin-top:6px">🪙 {item['cout']} or</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Forger", key=f"forge_{item['nom']}", disabled=not peut_acheter):
                conn = get_conn()
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE joueurs SET or_monnaie = or_monnaie - %s WHERE id = %s",
                        (item["cout"], joueur_id),
                    )
                    cur.execute("""
                        INSERT INTO equipements (joueur_id, nom, type, bonus_stat, valeur_bonus)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (joueur_id, item["nom"], item["type"], item["bonus_stat"], item["valeur_bonus"]))
                conn.commit()
                nouveaux = badge_engine.verifier_badges_forge(conn, joueur_id)
                conn.close()
                st.success(f"{item['nom']} forgé !")
                for code in nouveaux:
                    st.balloons()
                    st.success(f"🏅 Badge débloqué : **{code}** !")
                st.rerun()
    st.markdown("---")

# Inventaire et équipement
st.markdown("### 🎒 Inventaire")
equipements = db.get_equipements(joueur_id)
if not equipements:
    st.markdown("*Ton inventaire est vide. Forge ton premier équipement !*")
else:
    for item in equipements:
        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
        with c1:
            st.markdown(item["nom"])
        with c2:
            st.markdown(f"+{item['valeur_bonus']} {STAT_LABELS.get(item['bonus_stat'], item['bonus_stat'])}")
        with c3:
            statut = "✅ Equipé" if item["equipe"] else "—"
            st.markdown(statut)
        with c4:
            if not item["equipe"]:
                if st.button("Equiper", key=f"equip_{item['id']}"):
                    conn = get_conn()
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE equipements SET equipe = FALSE
                            WHERE joueur_id = %s AND type = %s
                        """, (joueur_id, item["type"]))
                        cur.execute(
                            "UPDATE equipements SET equipe = TRUE WHERE id = %s",
                            (item["id"],),
                        )
                    conn.commit()
                    nouveaux = badge_engine.verifier_badges_forge(conn, joueur_id)
                    conn.close()
                    for code in nouveaux:
                        st.balloons()
                        st.success(f"🏅 Badge débloqué : **{code}** !")
                    st.rerun()
