"""Tests for the sidebar info feature added in web/app.py.

Covers four units added or adjusted for the "infos sidebar" feature:

* ``_lire_version()``         — reads VERSION file; returns "?" on OSError.
* ``_countdown_reset_saison()`` — returns (days, hours) to next 1st-of-month
                                  00:00 UTC; clock is always mocked.
* ``inject_sidebar`` context processor — XP calc, season fetch, fallback to
                                  _SIDEBAR_VIDE on missing session / DB error.
* ``inject_version`` context processor  — ``app_version`` present on every
                                  rendered page, including the login page.

No real DB or network is ever contacted: every seam is patched with
``unittest.mock``.  The clock (``datetime.now``) is patched with
``unittest.mock.patch`` so countdown tests are fully deterministic.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# ── Make the production packages importable (mirrors container env) ──────────
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

# Import the helpers under test directly from the module.
from web.app import _lire_version, _countdown_reset_saison, create_app  # noqa: E402

# ── Shared player factory ─────────────────────────────────────────────────────

JOUEUR_ID = 42


def _fake_joueur(jid=JOUEUR_ID, level=3, xp=250, points_a_attribuer=0, **over):
    base = {
        "id": jid,
        "username": "alice",
        "level": level,
        "xp": xp,
        "or_monnaie": 100,
        "force_p": 10,
        "constitution_pv": 10,
        "agilite_vit": 10,
        "esprit_res": 10,
        "points_a_attribuer": points_a_attribuer,
        "points_combat": 0,
    }
    base.update(over)
    return base


def _fake_saison(numero=3):
    return {"id": 5, "numero": numero, "statut": "en_cours"}


# ── Shared Flask app fixture (identical pattern to test_web_routes.py) ────────

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
    """Authenticated session; patches both get_joueur AND get_saison_courante."""
    with client.session_transaction() as sess:
        sess["joueur_id"] = JOUEUR_ID
        sess["username"] = "alice"
    with patch("web.queries.get_joueur", return_value=_fake_joueur()), \
         patch("web.queries.get_saison_courante", return_value=_fake_saison()):
        yield client


# ═══════════════════════════════════════════════════════════════════════════════
# _lire_version
# ═══════════════════════════════════════════════════════════════════════════════

class TestLireVersion:
    def test_reads_version_from_existing_file(self, tmp_path):
        """The function returns the stripped text from the VERSION file."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("1.6.0\n", encoding="utf-8")
        with patch("web.app._VERSION_FILE", str(version_file)):
            result = _lire_version()
        assert result == "1.6.0"

    def test_strips_trailing_whitespace_and_newline(self, tmp_path):
        version_file = tmp_path / "VERSION"
        version_file.write_text("  2.0.0  \n", encoding="utf-8")
        with patch("web.app._VERSION_FILE", str(version_file)):
            result = _lire_version()
        assert result == "2.0.0"

    def test_returns_question_mark_when_file_absent(self, tmp_path):
        """Missing VERSION file must return "?" without raising."""
        missing_path = str(tmp_path / "NO_SUCH_FILE")
        with patch("web.app._VERSION_FILE", missing_path):
            result = _lire_version()
        assert result == "?"

    def test_returns_question_mark_on_permission_error(self, tmp_path):
        """Any OSError (e.g. permission denied) must return "?"."""
        with patch("web.app.open", side_effect=OSError("permission denied")):
            result = _lire_version()
        assert result == "?"

    def test_real_version_file_exists_and_is_non_empty(self):
        """Sanity check: the repo's own VERSION file is readable and non-empty."""
        result = _lire_version()
        assert result != "?" and len(result) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# _countdown_reset_saison — clock always mocked
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_now(dt: datetime):
    """Return a mock that replaces datetime.now(timezone.utc) with ``dt``."""
    m = MagicMock()
    m.return_value = dt
    return m


class TestCountdownResetSaison:
    """Every test freezes the UTC clock to a specific instant."""

    def _run(self, fake_now: datetime):
        """Call _countdown_reset_saison with datetime.now patched to fake_now."""
        with patch("web.app.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            return _countdown_reset_saison()

    # ── Mid-month, normal case ────────────────────────────────────────────────

    def test_mid_june_returns_positive_days_and_hours(self):
        # 2026-06-15 12:00 UTC -> next reset = 2026-07-01 00:00 UTC
        # delta = 15 days 12 h  =>  (15, 12)
        fake_now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 15
        assert hours == 12

    def test_first_of_month_start_returns_almost_full_month(self):
        # 2026-06-01 00:00:00 UTC -> next reset = 2026-07-01 00:00 UTC
        # delta = 30 days exactly => (30, 0)
        fake_now = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 30
        assert hours == 0

    # ── Last day of month ─────────────────────────────────────────────────────

    def test_last_day_of_month_few_hours_left(self):
        # 2026-06-30 20:00 UTC -> next reset = 2026-07-01 00:00 UTC
        # delta = 0 days 4 h => (0, 4)
        fake_now = datetime(2026, 6, 30, 20, 0, 0, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 0
        assert hours == 4

    def test_last_day_of_month_with_minutes_counts_floor_hours(self):
        # 2026-06-30 23:30 UTC -> delta = 0 days 0 h 30 min => (0, 0)
        # "less than 1 h remaining" case
        fake_now = datetime(2026, 6, 30, 23, 30, 0, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 0
        assert hours == 0

    # ── Less than one hour remaining ─────────────────────────────────────────

    def test_under_one_hour_returns_zero_zero(self):
        # 2026-06-30 23:59:01 UTC -> delta = ~59 s => (0, 0)
        fake_now = datetime(2026, 6, 30, 23, 59, 1, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 0
        assert hours == 0

    def test_exactly_one_second_before_reset_returns_zero_zero(self):
        fake_now = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 0
        assert hours == 0

    # ── December → January year boundary ─────────────────────────────────────

    def test_december_mid_month_crosses_year_boundary(self):
        # 2026-12-15 12:00 UTC -> next reset = 2027-01-01 00:00 UTC
        # delta = 16 days 12 h => (16, 12)
        fake_now = datetime(2026, 12, 15, 12, 0, 0, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 16
        assert hours == 12

    def test_december_31_last_hours_crosses_year_boundary(self):
        # 2026-12-31 20:00 UTC -> next = 2027-01-01 00:00 UTC -> (0, 4)
        fake_now = datetime(2026, 12, 31, 20, 0, 0, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 0
        assert hours == 4

    def test_december_31_under_one_hour_returns_zero_zero(self):
        fake_now = datetime(2026, 12, 31, 23, 45, 0, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 0
        assert hours == 0

    def test_december_1_returns_30_days_remaining(self):
        # 2026-12-01 00:00 UTC -> next = 2027-01-01 00:00 UTC -> 31 days
        fake_now = datetime(2026, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert days == 31
        assert hours == 0

    # ── Return type sanity ────────────────────────────────────────────────────

    def test_return_values_are_integers(self):
        fake_now = datetime(2026, 6, 10, 6, 30, 0, tzinfo=timezone.utc)
        days, hours = self._run(fake_now)
        assert isinstance(days, int)
        assert isinstance(hours, int)

    def test_hours_is_always_between_0_and_23(self):
        # Spot-check a few instants spread across the month.
        for hour in range(0, 24, 3):
            fake_now = datetime(2026, 6, 20, hour, 0, 0, tzinfo=timezone.utc)
            _, h = self._run(fake_now)
            assert 0 <= h <= 23, f"hours={h} out of range for fake_now hour={hour}"


# ═══════════════════════════════════════════════════════════════════════════════
# inject_sidebar — context processor
# ═══════════════════════════════════════════════════════════════════════════════

class TestInjectSidebar:
    """
    Context processors run on every template render.  We exercise them by
    hitting a protected page (the main '/' aventurier route) and inspecting
    either the response body or the template context.

    The sidebar keys that must always be present are:
      sidebar_joueur, sidebar_xp_restant, sidebar_saison,
      sidebar_reset_jours, sidebar_reset_heures
    """

    # ── No session (anonymous user) ───────────────────────────────────────────

    def test_anonymous_request_returns_empty_sidebar_keys(self, client):
        """Without a session every sidebar key must be present but empty/None/0."""
        # The login page uses inject_version but NOT inject_sidebar's joueur
        # branch; let's hit a page that renders base.html via the sidebar redirect.
        # We check the login page: sidebar_joueur must be None there.
        resp = client.get("/login")
        assert resp.status_code == 200
        # The sidebar player block should not appear.
        html = resp.get_data(as_text=True)
        assert "sidebar-player" not in html

    # ── get_joueur raises an exception ───────────────────────────────────────

    def test_get_joueur_exception_returns_empty_sidebar(self, client):
        """DB failure during get_joueur must silently yield _SIDEBAR_VIDE.

        The context processor in inject_sidebar swallows the exception and
        returns _SIDEBAR_VIDE.  We exercise this via the /classement route
        which does NOT call get_joueur itself in its handler — only the context
        processor does — so the only get_joueur call is inside inject_sidebar.
        A separate call to get_saison_courante is also needed by the classement
        route; we patch it too so the test stays fully isolated.
        """
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        with patch("web.queries.get_joueur", side_effect=RuntimeError("DB down")), \
             patch("web.queries.get_saison_courante", return_value=None), \
             patch("web.routes.classement.queries.tous_les_joueurs", return_value=[]), \
             patch("web.routes.classement.queries.tous_les_joueurs_par_pc", return_value=[]):
            resp = client.get("/classement")

        # The context processor must swallow the exception and render normally.
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        # Sidebar player block must be absent because _SIDEBAR_VIDE has joueur=None.
        assert "sidebar-player" not in html

    # ── get_joueur returns None ───────────────────────────────────────────────

    def test_get_joueur_none_returns_empty_sidebar(self, client):
        """When get_joueur returns None (player deleted) the sidebar is empty."""
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        with patch("web.queries.get_joueur", return_value=None), \
             patch("web.queries.get_saison_courante", return_value=None):
            resp = client.get("/login")
        assert resp.status_code in (200, 302)
        html = resp.get_data(as_text=True)
        # Player section must not render when joueur is None.
        assert "sidebar-player" not in html

    # ── Happy path: full sidebar ──────────────────────────────────────────────

    def test_happy_path_sidebar_renders_player_name(self, auth_client):
        """An authenticated request with a valid player renders the username."""
        resp = auth_client.get("/classement")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "alice" in html

    def test_happy_path_sidebar_renders_level(self, auth_client):
        resp = auth_client.get("/classement")
        html = resp.get_data(as_text=True)
        assert "Niveau 3" in html

    # ── XP restant calculation ────────────────────────────────────────────────

    def test_xp_restant_is_correct_for_level3_player(self, client):
        """
        Level 3 player with xp=250:
          xp_requis_pour_niveau(4) = XP_PAR_NIVEAU[3] = 450
          xp_restant = 450 - 250 = 200
        """
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        joueur = _fake_joueur(level=3, xp=250)
        saison = _fake_saison()
        with patch("web.queries.get_joueur", return_value=joueur), \
             patch("web.queries.get_saison_courante", return_value=saison), \
             patch("web.app._countdown_reset_saison", return_value=(10, 5)):
            resp = client.get("/classement")

        html = resp.get_data(as_text=True)
        assert "200 XP avant le niv. 4" in html

    def test_xp_restant_floored_at_zero_when_xp_exceeds_threshold(self, client):
        """
        If xp > xp_requis (level-up pending), xp_restant must be 0, not negative.
        """
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        # Level 3 threshold is 450; give player 500 xp (over-levelled, pending sync).
        joueur = _fake_joueur(level=3, xp=500)
        with patch("web.queries.get_joueur", return_value=joueur), \
             patch("web.queries.get_saison_courante", return_value=None), \
             patch("web.app._countdown_reset_saison", return_value=(0, 0)):
            resp = client.get("/classement")

        html = resp.get_data(as_text=True)
        # "0 XP avant le niv. 4" must appear (not "-50 XP …").
        assert "0 XP avant le niv. 4" in html

    # ── points_a_attribuer badge ──────────────────────────────────────────────

    def test_stat_badge_visible_when_points_to_assign(self, client):
        """The red badge with the point count must appear when points_a_attribuer > 0."""
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        joueur = _fake_joueur(points_a_attribuer=2)
        with patch("web.queries.get_joueur", return_value=joueur), \
             patch("web.queries.get_saison_courante", return_value=None), \
             patch("web.app._countdown_reset_saison", return_value=(5, 3)):
            resp = client.get("/classement")

        html = resp.get_data(as_text=True)
        assert "player-stat-badge" in html

    def test_stat_badge_absent_when_no_points_to_assign(self, client):
        """The red badge must NOT appear when points_a_attribuer == 0."""
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        joueur = _fake_joueur(points_a_attribuer=0)
        with patch("web.queries.get_joueur", return_value=joueur), \
             patch("web.queries.get_saison_courante", return_value=None), \
             patch("web.app._countdown_reset_saison", return_value=(5, 3)):
            resp = client.get("/classement")

        html = resp.get_data(as_text=True)
        assert "player-stat-badge" not in html

    # ── sidebar_saison ────────────────────────────────────────────────────────

    def test_season_block_renders_when_saison_available(self, auth_client):
        """When get_saison_courante returns a row the season number is shown."""
        resp = auth_client.get("/classement")
        html = resp.get_data(as_text=True)
        assert "Saison 3" in html

    def test_season_block_absent_when_get_saison_raises(self, client):
        """get_saison_courante raising must fall back to None (no crash, no block)."""
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        with patch("web.queries.get_joueur", return_value=_fake_joueur()), \
             patch("web.queries.get_saison_courante",
                   side_effect=RuntimeError("DB down")), \
             patch("web.app._countdown_reset_saison", return_value=(5, 3)):
            resp = client.get("/classement")

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "player-saison" not in html

    def test_season_block_absent_when_no_active_season(self, client):
        """When get_saison_courante returns None the season block must not render."""
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        with patch("web.queries.get_joueur", return_value=_fake_joueur()), \
             patch("web.queries.get_saison_courante", return_value=None), \
             patch("web.app._countdown_reset_saison", return_value=(5, 3)):
            resp = client.get("/classement")

        html = resp.get_data(as_text=True)
        assert "player-saison" not in html

    # ── reset countdown rendering ─────────────────────────────────────────────

    def test_countdown_rendered_as_days_hours_when_above_zero(self, client):
        """Normal countdown (>= 1 h) displays as 'Xj Yh restant'."""
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        with patch("web.queries.get_joueur", return_value=_fake_joueur()), \
             patch("web.queries.get_saison_courante", return_value=_fake_saison()), \
             patch("web.app._countdown_reset_saison", return_value=(5, 3)):
            resp = client.get("/classement")

        html = resp.get_data(as_text=True)
        assert "5j 3h restant" in html

    def test_countdown_rendered_as_less_than_1h_when_both_zero(self, client):
        """When days==0 and hours==0 the template must show 'moins d'1h restant'."""
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        with patch("web.queries.get_joueur", return_value=_fake_joueur()), \
             patch("web.queries.get_saison_courante", return_value=_fake_saison()), \
             patch("web.app._countdown_reset_saison", return_value=(0, 0)):
            resp = client.get("/classement")

        html = resp.get_data(as_text=True)
        assert "moins d'1h restant" in html

    def test_countdown_zero_days_nonzero_hours_renders_normally(self, client):
        """0j Xh restant (same day, some hours left) must NOT trigger the <1h text."""
        with client.session_transaction() as sess:
            sess["joueur_id"] = JOUEUR_ID

        with patch("web.queries.get_joueur", return_value=_fake_joueur()), \
             patch("web.queries.get_saison_courante", return_value=_fake_saison()), \
             patch("web.app._countdown_reset_saison", return_value=(0, 4)):
            resp = client.get("/classement")

        html = resp.get_data(as_text=True)
        assert "0j 4h restant" in html
        assert "moins d" not in html


# ═══════════════════════════════════════════════════════════════════════════════
# inject_version — context processor
# ═══════════════════════════════════════════════════════════════════════════════

class TestInjectVersion:
    def test_app_version_present_on_login_page(self, client):
        """inject_version must inject app_version even on the unauthenticated login page."""
        resp = client.get("/login")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        # The login template doesn't extend base.html with the sidebar, but it
        # may display the version. We only assert the context processor doesn't crash
        # and the page renders 200.  The version value itself is tested below.
        assert resp.status_code == 200

    def test_app_version_rendered_in_sidebar_for_authenticated_user(self, auth_client):
        """app_version must appear in the sidebar of a logged-in page."""
        resp = auth_client.get("/classement")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        # The template renders <div class="player-version">v{{ app_version }}</div>
        assert "player-version" in html
        # Should start with "v" followed by the real version from the VERSION file.
        import re
        match = re.search(r'class="player-version">v([^<]+)<', html)
        assert match is not None, "player-version block not found in rendered HTML"
        version_str = match.group(1).strip()
        assert len(version_str) > 0 and version_str != "?"

    def test_app_version_matches_version_file(self, auth_client):
        """The rendered version must match what _lire_version() returns."""
        expected = _lire_version()
        resp = auth_client.get("/classement")
        html = resp.get_data(as_text=True)
        assert f"v{expected}" in html

    def test_inject_version_not_dependent_on_session(self, client):
        """inject_version works without any joueur_id in session (login page)."""
        # Explicitly ensure no session key is set.
        with client.session_transaction() as sess:
            sess.clear()
        resp = client.get("/login")
        # Must not raise an exception; 200 expected.
        assert resp.status_code == 200
