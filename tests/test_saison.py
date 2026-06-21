"""Unit tests for the monthly season-reset system.

Three production seams are covered, all without any real PostgreSQL:

* ``worker._verifier_reset_saison`` — the idempotent monthly check. Every DB
  access it makes is a thin seam (``db.init_saison_si_absente``,
  ``db.get_saison_courante``, ``db.archiver_et_reset_saison``) plus a single
  cursor query that reads ``EXTRACT(DAY/YEAR/MONTH FROM NOW())`` from the DB
  clock. We patch the seams and feed the cursor a canned ``(day, year, month)``
  tuple so the branching logic is exercised in isolation.

* ``badge_engine.verifier_badges_saison`` — the season-badge attribution rules
  driven by the final rankings. ``db.attribuer_badge`` is mocked so we assert
  *which* badges are requested for *which* player given a rank.

* ``db.archiver_et_reset_saison`` — only the guard is unit-testable without a
  real DB: when no season is ``en_cours`` the first ``fetchone()`` is ``None``
  and the function must raise ``RuntimeError`` rather than archive garbage.

Integration paths that need a live PostgreSQL (the actual archive/reset SQL)
are intentionally NOT covered here — the project has no test database.
"""

from datetime import datetime, timezone
from unittest import mock

import pytest

import badge_engine
import db
import worker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _saison(numero=1, debut=None, statut="en_cours", sid=1):
    """A season row as ``db.get_saison_courante`` would return it."""
    if debut is None:
        debut = datetime(2026, 5, 1, tzinfo=timezone.utc)
    return {"id": sid, "numero": numero, "debut": debut, "fin": None, "statut": statut}


class _ClockCursor:
    """Minimal cursor whose single ``fetchone`` yields the DB clock tuple.

    ``_verifier_reset_saison`` runs exactly one query
    (``SELECT EXTRACT(DAY ...), EXTRACT(YEAR ...), EXTRACT(MONTH ...)``) and
    immediately unpacks ``cur.fetchone()`` into ``(day, year, month)``.
    """

    def __init__(self, day, year, month):
        self._row = (day, year, month)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._row


class _ClockConn:
    """Connection stub that hands out a single pre-programmed clock cursor."""

    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, *args, **kwargs):
        return self._cursor


# ═══════════════════════════════════════════════════════════════════════════
# worker._verifier_reset_saison — the monthly idempotent check
# ═══════════════════════════════════════════════════════════════════════════

class TestVerifierResetSaison:
    def test_returns_immediately_when_season_just_initialised(self):
        # init_saison_si_absente created season 1 -> nothing else must run:
        # no clock read, no current-season lookup, no reset.
        conn = mock.MagicMock()
        with mock.patch.object(worker.db, "init_saison_si_absente", return_value=True), \
             mock.patch.object(worker.db, "get_saison_courante") as get_saison, \
             mock.patch.object(worker.db, "archiver_et_reset_saison") as reset:
            worker._verifier_reset_saison(conn)

        get_saison.assert_not_called()
        reset.assert_not_called()
        conn.cursor.assert_not_called()

    def test_no_reset_when_not_first_of_month(self):
        # day=15 -> the function bails out before comparing the season month.
        conn = _ClockConn(_ClockCursor(day=15, year=2026, month=6))
        with mock.patch.object(worker.db, "init_saison_si_absente", return_value=False), \
             mock.patch.object(worker.db, "get_saison_courante",
                               return_value=_saison(debut=datetime(2026, 5, 1, tzinfo=timezone.utc))), \
             mock.patch.object(worker.db, "archiver_et_reset_saison") as reset:
            worker._verifier_reset_saison(conn)

        reset.assert_not_called()

    def test_no_reset_when_season_started_this_month(self):
        # day=1 but the current season began this very month/year -> already
        # reset for this cycle, must not reset again (idempotence guard).
        conn = _ClockConn(_ClockCursor(day=1, year=2026, month=6))
        with mock.patch.object(worker.db, "init_saison_si_absente", return_value=False), \
             mock.patch.object(worker.db, "get_saison_courante",
                               return_value=_saison(debut=datetime(2026, 6, 1, tzinfo=timezone.utc))), \
             mock.patch.object(worker.db, "archiver_et_reset_saison") as reset:
            worker._verifier_reset_saison(conn)

        reset.assert_not_called()

    def test_resets_when_first_of_month_and_season_is_older(self):
        # day=1 and the season began a previous month -> trigger the reset.
        conn = _ClockConn(_ClockCursor(day=1, year=2026, month=6))
        with mock.patch.object(worker.db, "init_saison_si_absente", return_value=False), \
             mock.patch.object(worker.db, "get_saison_courante",
                               return_value=_saison(debut=datetime(2026, 5, 1, tzinfo=timezone.utc))), \
             mock.patch.object(worker.db, "archiver_et_reset_saison") as reset:
            worker._verifier_reset_saison(conn)

        reset.assert_called_once_with(conn)

    def test_resets_when_season_started_same_month_but_previous_year(self):
        # day=1, same month number but a year earlier -> NOT "this month",
        # so the reset must fire (guard checks year AND month).
        conn = _ClockConn(_ClockCursor(day=1, year=2026, month=6))
        with mock.patch.object(worker.db, "init_saison_si_absente", return_value=False), \
             mock.patch.object(worker.db, "get_saison_courante",
                               return_value=_saison(debut=datetime(2025, 6, 1, tzinfo=timezone.utc))), \
             mock.patch.object(worker.db, "archiver_et_reset_saison") as reset:
            worker._verifier_reset_saison(conn)

        reset.assert_called_once_with(conn)

    def test_no_reset_when_no_current_season(self):
        # Table is non-empty (init returned False) yet no 'en_cours' row exists:
        # the function returns without touching the clock or the reset.
        conn = mock.MagicMock()
        with mock.patch.object(worker.db, "init_saison_si_absente", return_value=False), \
             mock.patch.object(worker.db, "get_saison_courante", return_value=None), \
             mock.patch.object(worker.db, "archiver_et_reset_saison") as reset:
            worker._verifier_reset_saison(conn)

        reset.assert_not_called()
        conn.cursor.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# badge_engine.verifier_badges_saison — season-badge attribution
# ═══════════════════════════════════════════════════════════════════════════

def _archive(joueur_id, rang_xp, rang_pc):
    return {"joueur_id": joueur_id, "rang_xp": rang_xp, "rang_pc": rang_pc}


class TestVerifierBadgesSaison:
    def test_rank1_xp_gets_champion_xp_and_podium(self):
        # rang_xp=1 -> champion XP; <=3 also qualifies for the podium badge.
        with mock.patch.object(badge_engine.db, "attribuer_badge", return_value=True) as attr:
            result = badge_engine.verifier_badges_saison(
                None, [_archive(7, rang_xp=1, rang_pc=5)]
            )

        assert result == {7: ["saison_champion_xp", "saison_podium"]}
        attr.assert_any_call(None, 7, "saison_champion_xp")
        # rang_pc=5 must NOT request the PC champion badge.
        for call in attr.call_args_list:
            assert call.args[2] != "saison_champion_pc"

    def test_rank1_pc_gets_champion_pc_and_podium(self):
        with mock.patch.object(badge_engine.db, "attribuer_badge", return_value=True) as attr:
            result = badge_engine.verifier_badges_saison(
                None, [_archive(8, rang_xp=5, rang_pc=1)]
            )

        assert result == {8: ["saison_champion_pc", "saison_podium"]}
        attr.assert_any_call(None, 8, "saison_champion_pc")
        for call in attr.call_args_list:
            assert call.args[2] != "saison_champion_xp"

    def test_rank2_xp_gets_podium_but_not_champion(self):
        # rang_xp=2 -> only the podium badge, never the champion badges.
        with mock.patch.object(badge_engine.db, "attribuer_badge", return_value=True) as attr:
            result = badge_engine.verifier_badges_saison(
                None, [_archive(9, rang_xp=2, rang_pc=4)]
            )

        assert result == {9: ["saison_podium"]}
        requested = [call.args[2] for call in attr.call_args_list]
        assert requested == ["saison_podium"]

    def test_rank4_both_gets_no_badge(self):
        # Outside the top 3 in both ladders -> no badge attempted at all.
        with mock.patch.object(badge_engine.db, "attribuer_badge", return_value=True) as attr:
            result = badge_engine.verifier_badges_saison(
                None, [_archive(10, rang_xp=4, rang_pc=4)]
            )

        assert result == {}
        attr.assert_not_called()

    def test_already_owned_badge_is_not_reported(self):
        # attribuer_badge returns False (badge already owned) -> the player must
        # not appear in the result, even though they ranked #1.
        with mock.patch.object(badge_engine.db, "attribuer_badge", return_value=False) as attr:
            result = badge_engine.verifier_badges_saison(
                None, [_archive(11, rang_xp=1, rang_pc=1)]
            )

        assert result == {}
        # The attribution was still attempted for each eligible badge.
        attempted = {call.args[2] for call in attr.call_args_list}
        assert attempted == {"saison_champion_xp", "saison_champion_pc", "saison_podium"}

    def test_multiple_players_aggregated_independently(self):
        with mock.patch.object(badge_engine.db, "attribuer_badge", return_value=True):
            result = badge_engine.verifier_badges_saison(
                None,
                [
                    _archive(1, rang_xp=1, rang_pc=3),
                    _archive(2, rang_xp=8, rang_pc=8),
                    _archive(3, rang_xp=3, rang_pc=1),
                ],
            )

        assert result == {
            1: ["saison_champion_xp", "saison_podium"],
            3: ["saison_champion_pc", "saison_podium"],
        }
        assert 2 not in result

    def test_empty_archives_returns_empty(self):
        with mock.patch.object(badge_engine.db, "attribuer_badge") as attr:
            result = badge_engine.verifier_badges_saison(None, [])

        assert result == {}
        attr.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# db.archiver_et_reset_saison — guard against running with no active season
# ═══════════════════════════════════════════════════════════════════════════

class _GuardCursor:
    """Cursor whose first (and only reached) fetchone returns ``None``."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return None


class _GuardConn:
    def __init__(self):
        self.committed = 0

    def cursor(self, *args, **kwargs):
        return _GuardCursor()

    def commit(self):
        self.committed += 1


class TestArchiverEtResetSaisonGuard:
    def test_raises_when_no_current_season(self):
        conn = _GuardConn()
        with pytest.raises(RuntimeError):
            db.archiver_et_reset_saison(conn)
        # No archive/reset transaction should have been committed.
        assert conn.committed == 0
