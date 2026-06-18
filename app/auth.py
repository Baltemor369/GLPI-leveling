# -*- coding: utf-8 -*-
"""Authentification GLPI OAuth2 pour GlpiLeveling — sessions par token URL."""

import base64
import json
import sys
import os
import uuid
from datetime import datetime, timedelta

import psycopg2.extras
import requests
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../sync"))
from config import GLPI_API_BASE_URL, GLPI_OAUTH_CLIENT_ID, GLPI_OAUTH_CLIENT_SECRET
from db import get_conn
import db_queries as db

TOKEN_URL = f"{GLPI_API_BASE_URL}/token"

SESSION_MINUTES = 15


# ── Gestion des tokens (persistés en BDD) ───────────────────────────────────

def _create_token(joueur_id: int, username: str) -> str:
    token = str(uuid.uuid4())
    expires = datetime.now() + timedelta(minutes=SESSION_MINUTES)
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE expires < NOW()")
        cur.execute(
            "INSERT INTO sessions (token, joueur_id, username, expires) VALUES (%s, %s, %s, %s)",
            (token, joueur_id, username, expires),
        )
    conn.commit()
    conn.close()
    return token


def _lookup_token(token: str) -> dict | None:
    conn = get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM sessions WHERE token = %s AND expires > NOW()",
            (token,),
        )
        sess = cur.fetchone()
        if sess:
            cur.execute(
                "UPDATE sessions SET expires = NOW() + make_interval(mins => %s) WHERE token = %s",
                (SESSION_MINUTES, token),
            )
    conn.commit()
    conn.close()
    return dict(sess) if sess else None


def _save_session(joueur_id: int, username: str):
    token = _create_token(joueur_id, username)
    st.session_state["joueur_id"] = joueur_id
    st.session_state["username"]  = username
    st.session_state["token"]     = token
    st.query_params["token"]      = token


def _restore_from_token() -> bool:
    token = st.query_params.get("token")
    if not token:
        return False
    sess = _lookup_token(token)
    if not sess:
        st.query_params.clear()
        return False
    st.session_state["joueur_id"] = sess["joueur_id"]
    st.session_state["username"]  = sess["username"]
    st.session_state["token"]     = token
    return True


def _clear_session():
    token = st.query_params.get("token")
    if token:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE token = %s", (token,))
        conn.commit()
        conn.close()
    st.query_params.clear()
    st.session_state.clear()


# ── JWT ─────────────────────────────────────────────────────────────────────

def _decode_jwt(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


# ── Login GLPI ──────────────────────────────────────────────────────────────

def login_glpi(username: str, password: str) -> dict | None:
    """Authentification OAuth2 GLPI. Retourne {"glpi_id", "username"} ou None."""
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type":    "password",
                "client_id":     GLPI_OAUTH_CLIENT_ID,
                "client_secret": GLPI_OAUTH_CLIENT_SECRET,
                "username":      username,
                "password":      password,
                "scope":         "api",
            },
            timeout=10,
        )
    except Exception:
        return None

    if resp.status_code != 200:
        return None

    token = resp.json().get("access_token")
    if not token:
        return None

    payload = _decode_jwt(token)
    sub = payload.get("sub") or payload.get("user_id") or payload.get("id")
    if sub is not None:
        try:
            return {"glpi_id": int(sub), "username": username}
        except (ValueError, TypeError):
            pass

    # Fallback : chercher par username dans joueurs
    joueurs = db.tous_les_joueurs()
    match = next((j for j in joueurs if j["username"].lower() == username.lower()), None)
    if match:
        return {"glpi_id": match["id"], "username": match["username"]}

    return {"glpi_id": None, "username": username}


# ── CSS ─────────────────────────────────────────────────────────────────────

_CSS_HIDE_SIDEBAR = """
<style>
section[data-testid="stSidebar"]          { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="stAppViewContainer"]        { margin-left: 0 !important; }
</style>
"""


def _show_login_form():
    from version import VERSION
    st.markdown(_CSS_HIDE_SIDEBAR, unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align:center;margin:60px 0 30px">
        <div style="font-family:'Cinzel',serif;color:#c9a84c;font-size:3rem;
                    text-shadow:0 0 20px rgba(201,168,76,0.5)">
            &#x2694;&nbsp;GLPILEVELING&nbsp;&#x2694;
        </div>
        <p style="color:#7a6a55;font-style:italic;font-size:1.1rem;margin-top:12px">
            Le Royaume du Helpdesk t'attend, Aventurier.
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1, 1])
    with col:
        with st.form("login_form"):
            st.markdown(
                "<div style='text-align:center;margin-bottom:16px'>"
                "<span style='font-family:Cinzel,serif;color:#c9a84c;font-size:1.1rem;"
                "letter-spacing:2px'>CONNEXION</span></div>",
                unsafe_allow_html=True,
            )
            username  = st.text_input("Identifiant GLPI", placeholder="prenom.nom")
            password  = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Entrer dans le Royaume", use_container_width=True)
            st.markdown(
                f"<div style='text-align:center;margin-top:12px;color:var(--gris);font-size:0.7rem'>"
                f"v{VERSION}</div>",
                unsafe_allow_html=True,
            )

        if submitted:
            if not username or not password:
                st.error("Remplis les deux champs.")
                return
            _spin = st.empty()
            _spin.markdown(
                "<div style='display:flex;align-items:center;gap:10px;padding:6px 0'>"
                "<div style='width:16px;height:16px;border-radius:50%;"
                "border:2px solid #8a6a1a;border-top-color:#c9a84c;"
                "animation:glpi-spin 0.7s linear infinite;flex-shrink:0'></div>"
                "<span style='color:#c9a84c;font-family:Cinzel,serif;"
                "font-size:0.78rem;letter-spacing:1.5px'>"
                "V&#xe9;rification des parchemins...</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            result = login_glpi(username, password)
            _spin.empty()
            if result is None:
                st.error("Identifiants GLPI incorrects.")
            elif result["glpi_id"] is None:
                st.warning(
                    "Connexion GLPI réussie, mais aucun ticket ne t'est encore assigné. "
                    "Ton profil sera créé dès ton premier ticket pris en charge."
                )
            else:
                _save_session(result["glpi_id"], result["username"])
                st.rerun()


# ── API publique ─────────────────────────────────────────────────────────────

def is_logged_in() -> bool:
    return "joueur_id" in st.session_state


def require_login(main_page: bool = False) -> int:
    """
    Vérifie l'authentification.
    - session_state présent → OK directement
    - sinon → lit le token dans l'URL et restaure la session depuis la DB
    - sinon → formulaire de login (main) ou redirect (sous-pages)
    """
    if "joueur_id" in st.session_state:
        # Réinjecte le token dans l'URL si la navigation l'a effacé
        # (sans ça, F5 sur une sous-page déconnecte car l'URL n'a plus de token)
        if "token" in st.session_state and not st.query_params.get("token"):
            st.query_params["token"] = st.session_state["token"]
        return st.session_state["joueur_id"]

    if _restore_from_token():
        return st.session_state["joueur_id"]

    if main_page:
        _show_login_form()
        st.stop()
    else:
        st.markdown(_CSS_HIDE_SIDEBAR, unsafe_allow_html=True)
        st.switch_page("Aventurier.py")


def render_sidebar():
    """Sidebar : identité du joueur connecté + bouton déconnexion."""
    with st.sidebar:
        st.markdown(
            "<h2 style='text-align:center;font-size:1.3rem'>&#x2694; GLPILEVELING</h2>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='ornement'>— ✦ —</div>", unsafe_allow_html=True)

        joueur = db.get_joueur(st.session_state["joueur_id"])
        nom    = joueur["username"]   if joueur else st.session_state["username"]
        niveau = joueur["level"]      if joueur else "—"
        or_val = joueur["or_monnaie"] if joueur else 0

        st.markdown(f"""
        <div style="text-align:center;padding:8px 0">
            <div style="color:var(--parchemin);font-size:1.05rem;font-weight:bold">{nom}</div>
            <div style="color:var(--gris);font-size:0.82rem">Niveau {niveau}</div>
            <div style="color:var(--or);font-size:0.85rem;margin-top:4px">&#x1F4B0; {or_val} or</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='ornement'>— ✦ —</div>", unsafe_allow_html=True)

        if st.button("D&#xe9;connexion", use_container_width=True, key="logout_btn"):
            _clear_session()
            st.rerun()
