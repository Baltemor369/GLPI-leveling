"""Page Forge — catalogue par tiers, améliorations +1 à +20, passifs."""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sync"))
import db_queries as db
import style
import psycopg2
from db import get_conn, get_materiaux, consommer_materiaux
import badge_engine

from auth import require_login, render_sidebar

st.set_page_config(page_title="Forge — GlpiLeveling", page_icon="🔨", layout="wide")
style.inject(st)

joueur_id = require_login()
render_sidebar()

st.markdown("# 🔨 La Forge")
st.markdown("*Dépense ton or pour forger des équipements et renforcer ton aventurier.*")
st.markdown("---")

joueur = db.get_joueur(joueur_id)
if not joueur:
    st.warning("Profil introuvable.")
    st.stop()

conn_mat  = get_conn()
stock_mat = get_materiaux(conn_mat, joueur_id)
conn_mat.close()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("💰 Or", joueur["or_monnaie"])
c2.metric("🌲 Bois de Chêne",  stock_mat.get("bois_chene",      0))
c3.metric("⚙️ Minerai de Fer", stock_mat.get("minerai_fer",     0))
c4.metric("💎 Cristal Runique",stock_mat.get("cristal_runique", 0))
c5.metric("✨ Essence du Néant",stock_mat.get("essence_neant",  0))
st.markdown("---")

# ── Catalogue ────────────────────────────────────────────────────────────────
CATALOGUE = [
    # ARMES
    {"nom": "Épée en Fer",        "type": "arme",   "bonus_stat": "force_p",        "valeur_bonus": 5,  "cout": 50,   "tier": 1, "passif_code": None,             "passif_desc": None},
    {"nom": "Lame d'Acier",       "type": "arme",   "bonus_stat": "force_p",        "valeur_bonus": 12, "cout": 150,  "tier": 2, "passif_code": None,             "passif_desc": None},
    {"nom": "Épée de Mithril",    "type": "arme",   "bonus_stat": "force_p",        "valeur_bonus": 22, "cout": 250,  "tier": 3, "passif_code": "saignement",     "passif_desc": "⚡ Saignement — 20% chance +3 dégâts bonus"},
    {"nom": "Lame Runique",       "type": "arme",   "bonus_stat": "force_p",        "valeur_bonus": 35, "cout": 500,  "tier": 4, "passif_code": "vampirisme",     "passif_desc": "💉 Vampirisme — récupère 25% des dégâts infligés"},
    {"nom": "Épée du Néant",      "type": "arme",   "bonus_stat": "force_p",        "valeur_bonus": 50, "cout": 2000, "tier": 5, "passif_code": "execution",      "passif_desc": "💀 Exécution — adverse < 20% PV → dégâts ×1.5"},
    # ARMURES
    {"nom": "Tunique de Cuir",    "type": "armure", "bonus_stat": "esprit_res",     "valeur_bonus": 5,  "cout": 50,   "tier": 1, "passif_code": None,             "passif_desc": None},
    {"nom": "Cotte de Mailles",   "type": "armure", "bonus_stat": "esprit_res",     "valeur_bonus": 12, "cout": 150,  "tier": 2, "passif_code": None,             "passif_desc": None},
    {"nom": "Armure de Plates",   "type": "armure", "bonus_stat": "esprit_res",     "valeur_bonus": 22, "cout": 250,  "tier": 3, "passif_code": "bouclier_pv",    "passif_desc": "🔰 Bouclier — +5% RES basé sur vos PV max"},
    {"nom": "Armure Runique",     "type": "armure", "bonus_stat": "esprit_res",     "valeur_bonus": 35, "cout": 500,  "tier": 4, "passif_code": "epines",         "passif_desc": "🔥 Épines — renvoie 15% des dégâts reçus"},
    {"nom": "Armure du Néant",    "type": "armure", "bonus_stat": "esprit_res",     "valeur_bonus": 50, "cout": 2000, "tier": 5, "passif_code": "immunite",       "passif_desc": "🛡️ Immunité — 25% chance d'ignorer les dégâts"},
    # AMULETTES
    {"nom": "Amulette de Vitalité","type": "amul",  "bonus_stat": "constitution_pv","valeur_bonus": 8,  "cout": 50,   "tier": 1, "passif_code": None,             "passif_desc": None},
    {"nom": "Bague de Célérité",  "type": "amul",   "bonus_stat": "agilite_vit",    "valeur_bonus": 6,  "cout": 150,  "tier": 2, "passif_code": None,             "passif_desc": None},
    {"nom": "Pendentif de l'Aube","type": "amul",   "bonus_stat": "constitution_pv","valeur_bonus": 15, "cout": 250,  "tier": 3, "passif_code": "regeneration",   "passif_desc": "💚 Régénération — récupère 5% PV max/tour"},
    {"nom": "Talisman Runique",   "type": "amul",   "bonus_stat": "agilite_vit",    "valeur_bonus": 10, "cout": 500,  "tier": 4, "passif_code": "celerite_niveau","passif_desc": "💨 Célérité — +0.5% esquive par niveau"},
    {"nom": "Orbe du Néant",      "type": "amul",   "bonus_stat": "constitution_pv","valeur_bonus": 20, "cout": 2000, "tier": 5, "passif_code": "transcendance",  "passif_desc": "✨ Transcendance — toutes les stats +1 par 2 niveaux"},
]

# Matériaux requis par tier (en plus de l'or)
MATERIAUX_REQUIS = {
    3: {"minerai_fer":     3},
    4: {"cristal_runique": 2},
    5: {"essence_neant":   1},
}
MAT_NOMS = {
    "bois_chene":      "🌲 Bois de Chêne",
    "minerai_fer":     "⚙️ Minerai de Fer",
    "cristal_runique": "💎 Cristal Runique",
    "essence_neant":   "✨ Essence du Néant",
}

TIER_LABELS  = {1: "Tier I", 2: "Tier II", 3: "Tier III", 4: "Tier IV", 5: "Tier V"}
TIER_COLORS  = {1: "#7a6a55", 2: "#8fbf8f", 3: "#6ab0e8", 4: "#c9a84c", 5: "#e05c5c"}
TYPE_LABELS  = {"arme": "⚔️ Armes", "armure": "🛡️ Armures", "amul": "📿 Amulettes"}
STAT_LABELS  = {
    "force_p": "Force", "esprit_res": "Résistance",
    "constitution_pv": "PV", "agilite_vit": "Agilité",
}

for type_key, type_label in TYPE_LABELS.items():
    st.markdown(f"### {type_label}")
    items = [i for i in CATALOGUE if i["type"] == type_key]
    cols  = st.columns(5)
    for col, item in zip(cols, items):
        with col:
            mat_requis   = MATERIAUX_REQUIS.get(item["tier"], {})
            assez_or     = joueur["or_monnaie"] >= item["cout"]
            assez_mat    = all(stock_mat.get(c, 0) >= q for c, q in mat_requis.items())
            peut_acheter = assez_or and assez_mat
            tier_color   = TIER_COLORS[item["tier"]]
            passif_html  = f"<div style='color:{tier_color};font-size:0.7rem;margin-top:4px'>{item['passif_desc']}</div>" if item["passif_desc"] else ""
            mat_html     = "".join(
                f"<div style='color:#6ab0e8;font-size:0.7rem'>{MAT_NOMS[c]} ×{q}</div>"
                for c, q in mat_requis.items()
            )
            st.markdown(f"""
            <div class="stat-card" style="{'opacity:0.45' if not peut_acheter else f'border:1px solid {tier_color}'}">
                <div style="color:{tier_color};font-size:0.7rem;font-weight:bold;letter-spacing:1px">{TIER_LABELS[item['tier']]}</div>
                <div class="stat-label" style="margin:4px 0">{item['nom']}</div>
                <div style="color:var(--parchemin);font-size:0.9rem">+{item['valeur_bonus']} {STAT_LABELS[item['bonus_stat']]}</div>
                <div style="color:var(--or);margin-top:6px">💰 {item['cout']}</div>
                {mat_html}
                {passif_html}
            </div>
            """, unsafe_allow_html=True)
            if st.button("Forger", key=f"forge_{item['nom']}", disabled=not peut_acheter):
                conn = get_conn()
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE joueurs SET or_monnaie = or_monnaie - %s "
                        "WHERE id = %s AND or_monnaie >= %s RETURNING id",
                        (item["cout"], joueur_id, item["cout"]),
                    )
                    if cur.fetchone() is None:
                        conn.rollback()
                        conn.close()
                        st.error("Or insuffisant.")
                        st.stop()
                    cur.execute("""
                        INSERT INTO equipements
                            (joueur_id, nom, type, bonus_stat, valeur_bonus,
                             passif_code, cout_base, tier)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (joueur_id, item["nom"], item["type"], item["bonus_stat"],
                          item["valeur_bonus"], item["passif_code"], item["cout"], item["tier"]))
                conn.commit()
                if mat_requis:
                    consommer_materiaux(conn, joueur_id, mat_requis)
                nouveaux = badge_engine.verifier_badges_forge(conn, joueur_id)
                conn.close()
                st.success(f"✅ {item['nom']} forgé !")
                for code in nouveaux:
                    st.balloons()
                    st.success(f"🏅 Badge débloqué : **{code}** !")
                st.rerun()
    st.markdown("---")

# ── Inventaire ────────────────────────────────────────────────────────────────
st.markdown("### 🎒 Inventaire & Améliorations")
equipements = db.get_equipements(joueur_id)

if not equipements:
    st.markdown("*Ton inventaire est vide. Forge ton premier équipement !*")
else:
    joueur = db.get_joueur(joueur_id)  # refresh or
    for item in equipements:
        amelioration = item.get("amelioration", 0)
        cout_base    = item.get("cout_base", 50)
        stat_totale  = item["valeur_bonus"] + amelioration * 2
        suffix       = f" +{amelioration}" if amelioration > 0 else ""
        tier_color   = TIER_COLORS.get(item.get("tier", 1), "#7a6a55")

        c1, c2, c3, c4, c5 = st.columns([3, 2, 1, 1, 2])
        with c1:
            st.markdown(f"<span style='color:{tier_color}'>{item['nom']}{suffix}</span>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"+{stat_totale} {STAT_LABELS.get(item['bonus_stat'], '')}")
        with c3:
            st.markdown("✅ Équipé" if item["equipe"] else "—")
        with c4:
            if not item["equipe"]:
                if st.button("Équiper", key=f"equip_{item['id']}"):
                    conn = get_conn()
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE equipements SET equipe = FALSE WHERE joueur_id = %s AND type = %s",
                            (joueur_id, item["type"]),
                        )
                        cur.execute("UPDATE equipements SET equipe = TRUE WHERE id = %s", (item["id"],))
                    conn.commit()
                    nouveaux = badge_engine.verifier_badges_forge(conn, joueur_id)
                    conn.close()
                    for code in nouveaux:
                        st.balloons()
                        st.success(f"🏅 Badge débloqué : **{code}** !")
                    st.rerun()
        with c5:
            if amelioration < 20:
                cout_base_upgrade = round(cout_base * (amelioration + 1) * 0.6)
                a_du_bois = stock_mat.get("bois_chene", 0) > 0
                cout_upgrade   = round(cout_base_upgrade * 0.7) if a_du_bois else cout_base_upgrade
                peut_ameliorer = joueur["or_monnaie"] >= cout_upgrade
                bois_label     = " 🌲-30%" if a_du_bois else ""
                label_btn      = f"⬆ +{amelioration + 1} (💰{cout_upgrade}{bois_label})"
                if st.button(label_btn, key=f"upgrade_{item['id']}", disabled=not peut_ameliorer):
                    conn = get_conn()
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE equipements SET amelioration = amelioration + 1 WHERE id = %s",
                            (item["id"],),
                        )
                        cur.execute(
                            "UPDATE joueurs SET or_monnaie = or_monnaie - %s "
                            "WHERE id = %s AND or_monnaie >= %s RETURNING id",
                            (cout_upgrade, joueur_id, cout_upgrade),
                        )
                        if cur.fetchone() is None:
                            conn.rollback()
                            conn.close()
                            st.error("Or insuffisant.")
                            st.stop()
                    conn.commit()
                    if a_du_bois:
                        consommer_materiaux(conn, joueur_id, {"bois_chene": 1})
                    conn.close()
                    st.success(f"✅ {item['nom']} amélioré à +{amelioration + 1} !")
                    st.rerun()
            else:
                st.markdown("<span style='color:var(--or)'>MAX</span>", unsafe_allow_html=True)
