# -*- coding: utf-8 -*-
"""Page Arène — Combats PvP au tour par tour."""

import html
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sync"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app"))

import streamlit as st
import db_queries as db
import style
from auth import require_login, render_sidebar
from db import get_conn
from combat_engine import (
    ACTIONS, creer_combat, accepter_combat,
    jouer_action, get_combat, get_combats_joueur,
    pv_max, force_effective, resistance_effective, agilite_effective, chance_esquive,
    _get_joueur, _get_equipements,
)
import psycopg2.extras

st.set_page_config(page_title="Arène — GlpiLeveling", page_icon="⚔️", layout="wide")
style.inject(st)

joueur_id = require_login()
render_sidebar()


def stats_joueur(conn, jid):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        j  = _get_joueur(cur, jid)
        eq = _get_equipements(cur, jid)
    return j, eq, pv_max(j, eq), force_effective(j, eq), resistance_effective(j, eq), agilite_effective(j, eq)


def afficher_fin_et_bouton_lobby(message, lobby_key, niveau="info"):
    """Affiche un message d'état final puis un bouton de retour au lobby.

    Utilisé par les fragments quand le combat/défi n'est plus dans un état jouable.
    `niveau` accepte "success" (st.success) ou toute autre valeur (st.info).
    `lobby_key` doit être unique par site d'appel pour éviter les conflits de clés
    Streamlit entre fragments distincts.
    Le `st.rerun(scope="app")` n'est déclenché que si l'utilisateur clique sur le
    bouton — il n'est pas appelé automatiquement à l'affichage du fragment.
    """
    (st.success if niveau == "success" else st.info)(message)
    if st.button("↩ Retourner au lobby", use_container_width=True, key=lobby_key):
        st.rerun(scope="app")


# ══════════════════════════════════════════════════════════════════════════
# FRAGMENT : COMBAT EN COURS (auto-refresh 3s)
# ══════════════════════════════════════════════════════════════════════════
@st.fragment(run_every=3)
def vue_combat_actif(combat_id, joueur_id):
    conn = get_conn()
    try:
        c = get_combat(conn, combat_id)
        if not c or c["statut"] != "en_cours":
            if c and c["statut"] == "termine":
                derniere = c["log_combat"].strip().split("\n")[-1] if c["log_combat"] else "Combat terminé."
                afficher_fin_et_bouton_lobby(derniere, "btn_lobby_fin", niveau="success")
            else:
                afficher_fin_et_bouton_lobby("Ce combat n'est plus disponible.", "btn_lobby_fin")
            return
        att_j, att_eq, att_pv_max, att_for, att_res, att_agi = stats_joueur(conn, c["attaquant_id"])
        def_j, def_eq, def_pv_max, def_for, def_res, def_agi = stats_joueur(conn, c["defenseur_id"])
    finally:
        conn.close()

    pv_att = c["pv_attaquant"]
    pv_def = c["pv_defenseur"]
    pct_att = max(0, int(pv_att / max(1, att_pv_max) * 100))
    pct_def = max(0, int(pv_def / max(1, def_pv_max) * 100))

    c_att_color = "#4caf50" if pct_att > 50 else "#ff9800" if pct_att > 25 else "#f44336"
    c_def_color = "#4caf50" if pct_def > 50 else "#ff9800" if pct_def > 25 else "#f44336"

    st.markdown("# &#x2694; Combat en cours !")
    if c["mise"] > 0:
        st.markdown(f"<div style='text-align:center;color:var(--or);font-size:1rem'>&#x1F4B0; Mise : {c['mise']} or chacun — Pot : <strong>{c['mise'] * 2} or</strong></div>", unsafe_allow_html=True)
    st.markdown("---")

    col_att, col_vs, col_def = st.columns([5, 1, 5])

    with col_att:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">ATTAQUANT</div>
            <div class="stat-value" style="font-size:1.4rem">{html.escape(att_j['username'])}</div>
            <div style="color:var(--gris);font-size:0.8rem">Niv. {att_j['level']}</div>
            <div style="margin:10px 0">
                <div style="display:flex;justify-content:space-between;font-size:0.8rem">
                    <span>PV</span><span style="color:{c_att_color}">{pv_att} / {att_pv_max}</span>
                </div>
                <div style="background:#1a0d00;border:1px solid #333;border-radius:4px;height:14px;margin-top:4px">
                    <div style="background:{c_att_color};width:{pct_att}%;height:100%;border-radius:4px"></div>
                </div>
            </div>
            <div style="font-size:0.8rem;color:var(--gris)">
                &#x2694; {att_for} &nbsp;|&nbsp; &#x1F6E1; {att_res} &nbsp;|&nbsp; &#x26A1; {att_agi}
            </div>
            <div style="font-size:0.75rem;color:#6ab0e8;margin-top:4px">
                Esquive : {chance_esquive(att_agi, def_for, att_j['level'], att_eq):.0%}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_vs:
        st.markdown("<div style='text-align:center;font-size:2rem;color:var(--or);padding-top:40px'>VS</div>",
                    unsafe_allow_html=True)

    with col_def:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">DÉFENSEUR</div>
            <div class="stat-value" style="font-size:1.4rem">{html.escape(def_j['username'])}</div>
            <div style="color:var(--gris);font-size:0.8rem">Niv. {def_j['level']}</div>
            <div style="margin:10px 0">
                <div style="display:flex;justify-content:space-between;font-size:0.8rem">
                    <span>PV</span><span style="color:{c_def_color}">{pv_def} / {def_pv_max}</span>
                </div>
                <div style="background:#1a0d00;border:1px solid #333;border-radius:4px;height:14px;margin-top:4px">
                    <div style="background:{c_def_color};width:{pct_def}%;height:100%;border-radius:4px"></div>
                </div>
            </div>
            <div style="font-size:0.8rem;color:var(--gris)">
                &#x2694; {def_for} &nbsp;|&nbsp; &#x1F6E1; {def_res} &nbsp;|&nbsp; &#x26A1; {def_agi}
            </div>
            <div style="font-size:0.75rem;color:#6ab0e8;margin-top:4px">
                Esquive : {chance_esquive(def_agi, att_for, def_j['level'], def_eq):.0%}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    mon_tour = (c["tour_de_qui"] == joueur_id)

    if mon_tour:
        st.markdown("### C'est ton tour — choisis ton action !")
        cols = st.columns(len(ACTIONS))
        for col, (aid, label, mult, desc, malus) in zip(cols, ACTIONS):
            with col:
                vitesse_txt = f"⚡ -{int(malus*100)}% vitesse" if malus > 0 else "⚡ Vitesse pleine"
                st.markdown(f"""
                <div class="stat-card" style="cursor:pointer">
                    <div class="stat-label">{label}</div>
                    <div style="color:var(--gris);font-size:0.75rem;margin:6px 0">{desc}</div>
                    <div style="color:var(--or);font-size:0.85rem">
                        {'&times;' + str(mult) if mult > 0 else '+15% PV'}
                    </div>
                    <div style="color:#6ab0e8;font-size:0.72rem;margin-top:4px">{vitesse_txt}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(label, key=f"action_{aid}"):
                    c2 = get_conn()
                    res = jouer_action(c2, c["id"], joueur_id, aid)
                    c2.close()
                    if res.get("nouveaux_badges"):
                        st.session_state["combat_badges"] = res["nouveaux_badges"]
                    st.rerun()
    else:
        adversaire = att_j["username"] if joueur_id == c["defenseur_id"] else def_j["username"]
        st.info(f"&#x23F3; En attente du tour de **{adversaire}**...")

    st.markdown("### &#x1F4DC; Journal de combat")
    lignes = c["log_combat"].strip().split("\n") if c["log_combat"] else []
    for ligne in reversed(lignes[-15:]):
        if ligne.strip():
            st.markdown(f"<div class='ticket-row'>{html.escape(ligne)}</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# FRAGMENT : DÉFI EN ATTENTE (auto-refresh 3s)
# ══════════════════════════════════════════════════════════════════════════
@st.fragment(run_every=3)
def vue_defi_attente(combat_id, joueur_id):
    conn = get_conn()
    try:
        combats = get_combats_joueur(conn, joueur_id)
        c = next((x for x in combats if x["id"] == combat_id), None)

        if not c or c["statut"] != "en_attente":
            if c and c["statut"] == "en_cours":
                afficher_fin_et_bouton_lobby(
                    "Le défi a été accepté ! Le combat est en cours.", "btn_lobby_defi", niveau="success"
                )
            else:
                afficher_fin_et_bouton_lobby(
                    "Ce défi a expiré ou n'est plus disponible.", "btn_lobby_defi"
                )
            return

        est_defenseur = (c["defenseur_id"] == joueur_id)

        if est_defenseur:
            mise_info = f" — Mise : **{c['mise']} or** chacun (pot : {c['mise'] * 2} or)" if c["mise"] > 0 else ""
            st.markdown(f"# &#x2694; Défi reçu de **{c['nom_attaquant']}** !")
            st.markdown(f"*{c['nom_attaquant']} te défie en combat{mise_info}. Acceptes-tu ?*")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Accepter le combat", use_container_width=True):
                    err = accepter_combat(conn, c["id"], joueur_id)
                    if err:
                        st.error(err)
                    else:
                        st.rerun(scope="app")
            with col2:
                if st.button("Refuser", use_container_width=True):
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM combats WHERE id = %s AND defenseur_id = %s",
                            (c["id"], joueur_id),
                        )
                    conn.commit()
                    st.rerun(scope="app")
        else:
            st.markdown(f"# &#x23F3; Défi envoyé à **{c['nom_defenseur']}**")
            st.info("En attente de sa réponse...")
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
# ROUTAGE
# ══════════════════════════════════════════════════════════════════════════
if "combat_badges" in st.session_state:
    for code in st.session_state.pop("combat_badges"):
        st.success(f"🏅 Badge débloqué : **{code}** !")

conn = get_conn()
combats_actifs    = get_combats_joueur(conn, joueur_id)
combat_en_cours   = next((c for c in combats_actifs if c["statut"] == "en_cours"),   None)
combat_en_attente = next((c for c in combats_actifs if c["statut"] == "en_attente"), None)
conn.close()

if combat_en_cours:
    vue_combat_actif(combat_en_cours["id"], joueur_id)

elif combat_en_attente:
    vue_defi_attente(combat_en_attente["id"], joueur_id)

# ══════════════════════════════════════════════════════════════════════════
# VUE : LOBBY
# ══════════════════════════════════════════════════════════════════════════
else:
    st.markdown("# &#x2694; Arène des Aventuriers")
    st.markdown("*Défie un collègue en combat singulier. Que le meilleur gagne !*")
    st.markdown("---")

    conn = get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT c.*, ja.username AS nom_attaquant, jd.username AS nom_defenseur
            FROM combats c
            JOIN joueurs ja ON ja.id = c.attaquant_id
            JOIN joueurs jd ON jd.id = c.defenseur_id
            WHERE (c.attaquant_id = %s OR c.defenseur_id = %s) AND c.statut = 'termine'
            ORDER BY c.id DESC LIMIT 1
        """, (joueur_id, joueur_id))
        dernier = cur.fetchone()
    conn.close()

    if dernier:
        st.markdown("### &#x1F4DC; Dernier combat")
        st.markdown(f"""
        <div class="ticket-row">
            <strong>{html.escape(dernier['nom_attaquant'])}</strong> vs <strong>{html.escape(dernier['nom_defenseur'])}</strong>
            <br><small style="color:var(--gris);white-space:pre-line">{html.escape(dernier['log_combat'][-300:])}</small>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")

    st.markdown("### Choisir un adversaire")
    try:
        tous_joueurs = db.tous_les_joueurs()
    except Exception:
        st.error("⚠️ Impossible de charger les joueurs (base de données indisponible ou migration en attente). Si la BDD est accessible : `docker compose up -d --build worker`")
        st.stop()

    adversaires    = [j for j in tous_joueurs if j["id"] != joueur_id]
    moi            = next((j for j in tous_joueurs if j["id"] == joueur_id), None)
    mon_or         = moi["or_monnaie"] if moi else 0

    if not adversaires:
        st.warning("Aucun autre aventurier disponible pour l'instant.")
    else:
        mise = st.number_input(
            f"Mise (or) — ton trésor : {mon_or} or",
            min_value=0, value=0, step=10,
            help="Les deux joueurs misent ce montant. Le vainqueur empoche le pot entier."
        )
        st.markdown("---")
        for adv in adversaires:
            col1, col2, col3, col4 = st.columns([3, 1, 1, 2])
            with col1:
                st.markdown(f"**{adv['username']}**")
            with col2:
                st.markdown(f"Niv. {adv['level']}")
            with col3:
                st.markdown(f"<span style='color:var(--or)'>&#x2B50; {adv['xp']} XP</span>",
                            unsafe_allow_html=True)
            with col4:
                if st.button("&#x2694; Défier", key=f"defi_{adv['id']}"):
                    conn = get_conn()
                    combat_id = creer_combat(conn, joueur_id, adv["id"], mise)
                    conn.close()
                    label = f" pour {mise} or" if mise > 0 else ""
                    st.success(f"Défi envoyé à {adv['username']}{label} !")
                    time.sleep(1)
                    st.rerun()
