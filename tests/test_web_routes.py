"""Tests for the Flask frontend routes under ``web/``.

These tests exercise the HTTP layer of the application (blueprints in
``web/routes/``) in isolation: every database / auth seam is mocked with
``unittest.mock`` so **no real PostgreSQL connection or GLPI call is made**.

Why mocking instead of a DB:
``web`` is wired like the container (``PYTHONPATH=/app/sync:/app``), so it
imports ``config``, ``db`` and ``combat_engine`` from ``sync/``. The route
handlers call thin seams (``queries.get_joueur``, ``arene.get_combat``,
``forge.get_conn`` …). We patch those seams and assert on status codes,
redirects, session state and flashed messages — the actual behaviour of the
route, not the DB.

What is covered:
* ``/login`` GET + POST (valid, invalid, missing fields, no-profile warning).
* ``login_required`` redirect for every protected route when unauthenticated.
* ``/logout`` clears the session.
* ``/arene/combat-partial`` guards: missing ``combat_id`` (286 stop-polling),
  unknown combat (286), IDOR — combat owned by another player (286).
* ``/arene/action`` guard: missing ``combat_id`` -> redirect to ``/arene``.
* ``/forge/acheter``: unknown item, insufficient gold, insufficient materials,
  happy path.
* ``/stat/depenser``: invalid stat, no point available, success.
* ``/expedition/lancer`` and ``/expedition/reclamer`` (no active expedition).
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ── Importability + dummy env (mirrors the container PYTHONPATH=/app/sync:/app)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SYNC_DIR = os.path.join(_PROJECT_ROOT, "sync")
for _p in (_SYNC_DIR, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("GLPI_API_BASE_URL", "http://test")
os.environ.setdefault("GLPI_OAUTH_CLIENT_ID", "test")
os.environ.setdefault("GLPI_OAUTH_CLIENT_SECRET", "test")
os.environ.setdefault("GLPI_BOT_USERNAME", "test")
os.environ.setdefault("GLPI_BOT_PASSWORD", "test")

from web.app import create_app  # noqa: E402


JOUEUR_ID = 42
OTHER_ID = 99

# HTMX stops polling a fragment when the response status is 286.
HTMX_STOP_POLLING = 286


def _fake_joueur(jid=JOUEUR_ID, **over):
    """Minimal player row good enough for the sidebar context processor and
    the aventurier/forge pages."""
    base = {
        "id": jid,
        "username": "alice",
        "level": 3,
        "xp": 250,
        "or_monnaie": 100,
        "force_p": 10,
        "constitution_pv": 10,
        "agilite_vit": 10,
        "esprit_res": 10,
        "points_a_attribuer": 2,
        "points_combat": 0,
    }
    base.update(over)
    return base


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(client):
    """A test client with an authenticated session.

    The sidebar context processor calls ``queries.get_joueur`` on every render
    of a page that has a session, so we patch it for the whole authed-client
    lifetime to keep template rendering from hitting the DB.
    """
    with client.session_transaction() as sess:
        sess["joueur_id"] = JOUEUR_ID
        sess["username"] = "alice"
    with patch("web.queries.get_joueur", return_value=_fake_joueur()):
        yield client


# ── /login ──────────────────────────────────────────────────────────────────

class TestLogin:
    def test_get_login_returns_200(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200

    def test_already_logged_in_redirects_to_index(self, client):
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID
        resp = client.get("/login")
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "http://localhost/")

    def test_valid_post_creates_session_and_redirects(self, client):
        with patch(
            "web.routes.auth.login_glpi",
            return_value={"glpi_id": JOUEUR_ID, "username": "alice"},
        ) as mock_login:
            resp = client.post(
                "/login", data={"username": "alice", "password": "secret"}
            )
        mock_login.assert_called_once_with("alice", "secret")
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "http://localhost/")
        with client.session_transaction() as sess:
            assert sess["joueur_id"] == JOUEUR_ID
            assert sess["username"] == "alice"

    def test_invalid_credentials_no_session_renders_login(self, client):
        with patch("web.routes.auth.login_glpi", return_value=None):
            resp = client.post(
                "/login", data={"username": "alice", "password": "bad"}
            )
        assert resp.status_code == 200
        assert "Identifiants GLPI incorrects." in resp.get_data(as_text=True)
        with client.session_transaction() as sess:
            assert "joueur_id" not in sess

    def test_missing_fields_does_not_call_login(self, client):
        with patch("web.routes.auth.login_glpi") as mock_login:
            resp = client.post("/login", data={"username": "", "password": ""})
        mock_login.assert_not_called()
        assert resp.status_code == 200
        assert "Remplis les deux champs." in resp.get_data(as_text=True)

    def test_login_without_assigned_ticket_warns_and_no_session(self, client):
        # GLPI auth succeeds but the player has no profile yet (glpi_id None).
        with patch(
            "web.routes.auth.login_glpi",
            return_value={"glpi_id": None, "username": "bob"},
        ):
            resp = client.post(
                "/login", data={"username": "bob", "password": "secret"}
            )
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert "joueur_id" not in sess

    def test_logout_clears_session(self, client):
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID
            sess["username"] = "alice"
        resp = client.get("/logout")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]
        with client.session_transaction() as sess:
            assert "joueur_id" not in sess


# ── login_required on every protected route ───────────────────────────────────

PROTECTED_GET = [
    "/",
    "/arene",
    "/arene/combat-partial",
    "/arene/attente-partial",
    "/forge",
    "/expedition",
    "/expedition/status",
    "/badges",
    "/journal",
    "/classement",
]

PROTECTED_POST = [
    "/stat/depenser",
    "/arene/defier",
    "/arene/action",
    "/arene/accepter/1",
    "/arene/refuser/1",
    "/forge/acheter",
    "/forge/equiper/1",
    "/forge/ameliorer/1",
    "/expedition/lancer",
    "/expedition/reclamer",
]


class TestAuthGuard:
    @pytest.mark.parametrize("url", PROTECTED_GET)
    def test_protected_get_redirects_to_login_when_anonymous(self, client, url):
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    @pytest.mark.parametrize("url", PROTECTED_POST)
    def test_protected_post_redirects_to_login_when_anonymous(self, client, url):
        resp = client.post(url)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ── /arene/combat-partial guards (combat_id=None, unknown, IDOR) ──────────────

class TestCombatPartial:
    def test_missing_combat_id_returns_286_stop_polling(self, auth_client):
        # No combat_id => fragment with a message and the stop-polling status.
        resp = auth_client.get("/arene/combat-partial")
        assert resp.status_code == HTMX_STOP_POLLING

    def test_unknown_combat_returns_286(self, auth_client):
        with patch("web.routes.arene.get_conn", return_value=MagicMock()), \
             patch("web.routes.arene.get_combat", return_value=None):
            resp = auth_client.get("/arene/combat-partial?combat_id=123")
        assert resp.status_code == HTMX_STOP_POLLING

    def test_combat_owned_by_other_player_is_refused_idor(self, auth_client):
        # Combat between two *other* players: the session player is neither the
        # attacker nor the defender -> access refused, stop polling (286).
        foreign_combat = {
            "id": 123,
            "attaquant_id": OTHER_ID,
            "defenseur_id": OTHER_ID + 1,
            "statut": "en_cours",
        }
        with patch("web.routes.arene.get_conn", return_value=MagicMock()), \
             patch("web.routes.arene.get_combat", return_value=foreign_combat):
            resp = auth_client.get("/arene/combat-partial?combat_id=123")
        assert resp.status_code == HTMX_STOP_POLLING
        assert "Accès refusé." in resp.get_data(as_text=True)

    def test_finished_combat_returns_286(self, auth_client):
        finished = {
            "id": 123,
            "attaquant_id": JOUEUR_ID,
            "defenseur_id": OTHER_ID,
            "statut": "termine",
            "vainqueur_id": JOUEUR_ID,
            "log_combat": "alice gagne !",
        }
        with patch("web.routes.arene.get_conn", return_value=MagicMock()), \
             patch("web.routes.arene.get_combat", return_value=finished):
            resp = auth_client.get("/arene/combat-partial?combat_id=123")
        assert resp.status_code == HTMX_STOP_POLLING


# ── /arene/action guard ───────────────────────────────────────────────────────

class TestAreneAction:
    def test_missing_combat_id_redirects_to_arene(self, auth_client):
        # jouer_action must never be reached when combat_id is absent.
        with patch("web.routes.arene.jouer_action") as mock_play:
            resp = auth_client.post("/arene/action", data={"action_id": "attaque"})
        mock_play.assert_not_called()
        assert resp.status_code == 302
        assert "/arene" in resp.headers["Location"]


# ── /forge/acheter ────────────────────────────────────────────────────────────

class TestForgeAcheter:
    def test_unknown_item_redirects_to_forge(self, auth_client):
        resp = auth_client.post("/forge/acheter", data={"nom": "Cuillère Magique"})
        assert resp.status_code == 302
        assert "/forge" in resp.headers["Location"]

    def test_insufficient_gold_rolls_back_and_redirects(self, auth_client):
        # Tier-1 item (no materials). The conditional UPDATE matches no row
        # (fetchone -> None) => rollback + "Or insuffisant." flash.
        cur = MagicMock()
        cur.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur

        with patch("web.routes.forge.get_conn", return_value=conn):
            resp = auth_client.post(
                "/forge/acheter", data={"nom": "Épée en Fer"}
            )

        assert resp.status_code == 302
        assert "/forge" in resp.headers["Location"]
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
        # Follow the redirect to read the flashed error message. The forge
        # index also hits the DB, so its seams are mocked too.
        with patch("web.routes.forge.get_conn", return_value=conn), \
             patch("web.routes.forge.get_materiaux", return_value={}), \
             patch("web.queries.get_equipements", return_value=[]):
            resp2 = auth_client.get("/forge")
        assert "Or insuffisant." in resp2.get_data(as_text=True)

    def test_insufficient_materials_blocks_before_write(self, auth_client):
        # Tier-3 item requires minerai_fer x3; stock is empty -> early redirect,
        # no gold debit attempted.
        conn = MagicMock()
        with patch("web.routes.forge.get_conn", return_value=conn), \
             patch("web.routes.forge.get_materiaux", return_value={"minerai_fer": 0}):
            resp = auth_client.post(
                "/forge/acheter", data={"nom": "Épée de Mithril"}
            )
        assert resp.status_code == 302
        assert "/forge" in resp.headers["Location"]
        conn.commit.assert_not_called()

    def test_successful_purchase_commits_and_redirects(self, auth_client):
        # Sufficient gold: UPDATE returns a row id, INSERT runs, commit happens.
        cur = MagicMock()
        cur.fetchone.return_value = (JOUEUR_ID,)
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur

        with patch("web.routes.forge.get_conn", return_value=conn), \
             patch("web.routes.forge.badge_engine") as mock_badge:
            mock_badge.verifier_badges_forge.return_value = []
            resp = auth_client.post(
                "/forge/acheter", data={"nom": "Épée en Fer"}
            )

        assert resp.status_code == 302
        assert "/forge" in resp.headers["Location"]
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()


# ── /stat/depenser ────────────────────────────────────────────────────────────

class TestDepenserStat:
    def test_invalid_stat_flashes_error_and_redirects(self, auth_client):
        # The real queries.depenser_point_stat raises ValueError on a bad stat;
        # the route must catch it and redirect (not 500).
        with patch(
            "web.queries.depenser_point_stat",
            side_effect=ValueError("Stat invalide : hp"),
        ) as mock_dep:
            resp = auth_client.post("/stat/depenser", data={"stat": "hp"})
        mock_dep.assert_called_once_with(JOUEUR_ID, "hp")
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "http://localhost/")

    def test_no_point_available_redirects(self, auth_client):
        with patch("web.queries.depenser_point_stat", return_value=False):
            resp = auth_client.post(
                "/stat/depenser", data={"stat": "force_p"}
            )
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "http://localhost/")

    def test_successful_spend_redirects_to_index(self, auth_client):
        with patch("web.queries.depenser_point_stat", return_value=True) as mock_dep:
            resp = auth_client.post(
                "/stat/depenser", data={"stat": "constitution_pv"}
            )
        mock_dep.assert_called_once_with(JOUEUR_ID, "constitution_pv")
        assert resp.status_code == 302
        assert resp.headers["Location"] in ("/", "http://localhost/")


# ── /expedition ───────────────────────────────────────────────────────────────

class TestExpedition:
    def test_lancer_starts_expedition_and_redirects(self, auth_client):
        conn = MagicMock()
        with patch("web.routes.expedition.get_conn", return_value=conn), \
             patch("web.routes.expedition.lancer_expedition") as mock_lancer:
            resp = auth_client.post("/expedition/lancer")
        mock_lancer.assert_called_once()
        assert resp.status_code == 302
        assert "/expedition" in resp.headers["Location"]

    def test_reclamer_without_active_expedition_redirects(self, auth_client):
        conn = MagicMock()
        with patch("web.routes.expedition.get_conn", return_value=conn), \
             patch("web.routes.expedition.get_expedition_active", return_value=None):
            resp = auth_client.post("/expedition/reclamer")
        assert resp.status_code == 302
        assert "/expedition" in resp.headers["Location"]
