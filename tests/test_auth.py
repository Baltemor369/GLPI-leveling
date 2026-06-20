# -*- coding: utf-8 -*-
"""Tests for the GLPI-id resolution helpers in ``app/auth.py``.

``login_glpi()`` was decomposed into three private helpers; two of them carry
all the parsing/lookup logic and are unit-testable in isolation:

* ``_glpi_id_from_token(token)`` — pure: decodes the JWT payload and extracts a
  numeric GLPI user id from ``sub`` / ``user_id`` / ``id`` (in that order),
  returning ``None`` when absent or non-numeric.
* ``_glpi_id_from_username(username)`` — looks the player up by username
  (case-insensitive) through the ``db_queries.tous_les_joueurs`` seam, and
  swallows DB errors by returning ``None``.

``app/auth.py`` imports ``requests`` and ``streamlit`` at module load, neither
of which is part of the test environment (and neither is used by the two
helpers under test). Following the suite's "no real services" philosophy we
register lightweight stand-ins in ``sys.modules`` *before* importing the module,
exactly mirroring how ``conftest.py`` injects dummy config so production modules
import cleanly. The DB is never contacted: ``tous_les_joueurs`` is mocked.
"""

import base64
import json
import os
import sys
import types

import pytest


# ── Make ``app/`` importable (auth.py lives there, alongside db_queries) ─────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.join(_PROJECT_ROOT, "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)


# ── Stub the heavy/optional deps auth.py imports but the helpers never use ───
# ``requests`` and ``streamlit`` are absent from the test env; the functions we
# test (``_glpi_id_from_token`` / ``_glpi_id_from_username``) touch neither.
def _install_import_stubs():
    if "requests" not in sys.modules:
        requests_stub = types.ModuleType("requests")
        requests_stub.post = lambda *a, **k: None  # never called in these tests
        sys.modules["requests"] = requests_stub

    if "streamlit" not in sys.modules:
        st_stub = types.ModuleType("streamlit")
        # auth.py references st.session_state / st.query_params at runtime only;
        # nothing at import time beyond the module object itself.
        st_stub.session_state = {}
        st_stub.query_params = {}
        sys.modules["streamlit"] = st_stub


_install_import_stubs()

import auth  # noqa: E402  (import after stubs are registered)


# ── Helper: build a JWT-shaped token with a chosen payload ──────────────────

def make_jwt(payload: dict) -> str:
    """Return a ``header.payload.signature`` token whose middle segment is the
    urlsafe-base64 of ``payload`` — the only part ``_decode_jwt`` reads."""
    raw = json.dumps(payload).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    return f"header.{body}.signature"


# ═══════════════════════════════════════════════════════════════════════════
# _glpi_id_from_token
# ═══════════════════════════════════════════════════════════════════════════

class TestGlpiIdFromToken:
    def test_extracts_sub_claim_as_int(self):
        assert auth._glpi_id_from_token(make_jwt({"sub": 42})) == 42

    def test_extracts_numeric_sub_given_as_string(self):
        # GLPI may serialise the subject as a string; it must still parse.
        assert auth._glpi_id_from_token(make_jwt({"sub": "42"})) == 42

    def test_falls_back_to_user_id_when_sub_absent(self):
        assert auth._glpi_id_from_token(make_jwt({"user_id": 7})) == 7

    def test_falls_back_to_id_when_sub_and_user_id_absent(self):
        assert auth._glpi_id_from_token(make_jwt({"id": 9})) == 9

    def test_sub_takes_precedence_over_user_id_and_id(self):
        token = make_jwt({"sub": 1, "user_id": 2, "id": 3})
        assert auth._glpi_id_from_token(token) == 1

    def test_user_id_takes_precedence_over_id(self):
        token = make_jwt({"user_id": 2, "id": 3})
        assert auth._glpi_id_from_token(token) == 2

    def test_returns_none_when_no_id_claim_present(self):
        assert auth._glpi_id_from_token(make_jwt({"email": "a@b.c"})) is None

    def test_returns_none_when_sub_is_non_numeric(self):
        assert auth._glpi_id_from_token(make_jwt({"sub": "not-a-number"})) is None

    def test_returns_none_for_malformed_token(self):
        # No second segment -> _decode_jwt returns {} -> no claim -> None.
        assert auth._glpi_id_from_token("garbage") is None

    def test_returns_none_for_empty_token(self):
        assert auth._glpi_id_from_token("") is None

    def test_sub_zero_falls_through_or_chain_and_yields_none(self):
        # Known limitation: the extraction uses
        #   sub = payload.get("sub") or payload.get("user_id") or payload.get("id")
        # so a claim value of 0 (falsy) is skipped and, with no other claim
        # present, the function returns None rather than 0. GLPI user ids are
        # never 0 in practice (system ids start at 2), so this has no real
        # impact — but this test pins the behaviour so a future change is
        # noticed. See the report's Notes for the bug write-up.
        assert auth._glpi_id_from_token(make_jwt({"sub": 0})) is None

    def test_sub_zero_with_fallback_user_id_uses_fallback(self):
        # Direct consequence of the falsy-0 fall-through: a 0 ``sub`` lets a
        # later non-zero claim win instead of the (valid) 0.
        token = make_jwt({"sub": 0, "user_id": 5})
        assert auth._glpi_id_from_token(token) == 5

    def test_negative_id_is_parsed(self):
        assert auth._glpi_id_from_token(make_jwt({"sub": -5})) == -5


# ═══════════════════════════════════════════════════════════════════════════
# _glpi_id_from_username  (db seam mocked)
# ═══════════════════════════════════════════════════════════════════════════

class TestGlpiIdFromUsername:
    @pytest.fixture
    def players(self):
        return [
            {"id": 1, "username": "Alice"},
            {"id": 2, "username": "Bob"},
            {"id": 3, "username": "Carol.Dupont"},
        ]

    def _patch_players(self, monkeypatch, value_or_exc):
        if isinstance(value_or_exc, Exception):
            def boom():
                raise value_or_exc
            monkeypatch.setattr(auth.db, "tous_les_joueurs", boom)
        else:
            monkeypatch.setattr(
                auth.db, "tous_les_joueurs", lambda: value_or_exc
            )

    def test_returns_matching_player_on_exact_username(self, monkeypatch, players):
        self._patch_players(monkeypatch, players)
        match = auth._glpi_id_from_username("Bob")
        assert match == {"id": 2, "username": "Bob"}

    def test_match_is_case_insensitive(self, monkeypatch, players):
        self._patch_players(monkeypatch, players)
        match = auth._glpi_id_from_username("aLiCe")
        assert match["id"] == 1

    def test_matches_username_with_dot(self, monkeypatch, players):
        self._patch_players(monkeypatch, players)
        match = auth._glpi_id_from_username("carol.dupont")
        assert match["id"] == 3

    def test_returns_none_when_no_username_matches(self, monkeypatch, players):
        self._patch_players(monkeypatch, players)
        assert auth._glpi_id_from_username("Eve") is None

    def test_returns_none_on_empty_player_list(self, monkeypatch):
        self._patch_players(monkeypatch, [])
        assert auth._glpi_id_from_username("Alice") is None

    def test_returns_none_when_db_raises(self, monkeypatch):
        # The try/except wrapper must swallow DB failures and yield None,
        # not propagate the exception up into the login flow.
        self._patch_players(monkeypatch, RuntimeError("db down"))
        assert auth._glpi_id_from_username("Alice") is None

    def test_returns_first_match_when_usernames_collide(self, monkeypatch):
        # Defensive: if the DB ever returns duplicate usernames, the first wins.
        dupes = [
            {"id": 10, "username": "Dup"},
            {"id": 11, "username": "dup"},
        ]
        self._patch_players(monkeypatch, dupes)
        match = auth._glpi_id_from_username("DUP")
        assert match["id"] == 10
