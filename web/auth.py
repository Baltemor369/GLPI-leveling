"""Authentification GLPI OAuth2 + gestion de session Flask (cookie HTTP)."""

import base64
import json
from functools import wraps

import requests
from flask import session, redirect, url_for

from config import GLPI_API_BASE_URL, GLPI_OAUTH_CLIENT_ID, GLPI_OAUTH_CLIENT_SECRET
from . import queries

TOKEN_URL = f"{GLPI_API_BASE_URL}/token"
REQUEST_TIMEOUT = 10


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "joueur_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def _request_access_token(username: str, password: str) -> str | None:
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
            timeout=REQUEST_TIMEOUT,
        )
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    return resp.json().get("access_token")


def _glpi_id_from_token(token: str) -> int | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None
    sub = data.get("sub") or data.get("user_id") or data.get("id")
    if sub is None:
        return None
    try:
        return int(sub)
    except (ValueError, TypeError):
        return None


def _glpi_id_from_username(username: str) -> dict | None:
    try:
        joueurs = queries.tous_les_joueurs()
    except Exception:
        return None
    return next(
        (j for j in joueurs if j["username"].lower() == username.lower()),
        None,
    )


def login_glpi(username: str, password: str) -> dict | None:
    """Retourne {"glpi_id": int, "username": str} ou None si identifiants invalides."""
    token = _request_access_token(username, password)
    if not token:
        return None

    glpi_id = _glpi_id_from_token(token)
    if glpi_id is not None:
        return {"glpi_id": glpi_id, "username": username}

    match = _glpi_id_from_username(username)
    if match:
        return {"glpi_id": match["id"], "username": match["username"]}

    return {"glpi_id": None, "username": username}
