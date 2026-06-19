"""Tests for the atomic gold-debit contract used by the Forge page.

``app/pages/3_Forge.py`` is a Streamlit *script*: importing it executes the
whole page (``st.set_page_config``, ``require_login()``, DB calls, widget
rendering), so it cannot be imported in isolation for a unit test.

What matters for correctness is the **atomic debit** pattern it relies on:

    UPDATE joueurs SET or_monnaie = or_monnaie - %s
    WHERE id = %s AND or_monnaie >= %s RETURNING id

When the player does not have enough gold the conditional ``UPDATE`` matches no
row, ``RETURNING id`` yields nothing, ``cur.fetchone()`` is ``None`` and the
code must ``conn.rollback()`` instead of inserting the item.

These tests:

1. Exercise that debit-then-branch logic against a mocked psycopg2 cursor,
   covering both the sufficient-funds and insufficient-funds outcomes.
2. Assert that the production source files still contain the exact atomic SQL
   and the ``rollback()`` guard, so the behaviour under test stays anchored to
   the real code (the test fails if someone weakens the guard).
"""

import os
import re

import pytest

from test_combat_engine import FakeConn, FakeCursor


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORGE_PATH = os.path.join(PROJECT_ROOT, "app", "pages", "3_Forge.py")


@pytest.fixture(scope="module")
def forge_source():
    with open(FORGE_PATH, encoding="utf-8") as fh:
        return fh.read()


# ── Faithful replica of the production debit snippet ────────────────────────
# Mirrors the ``Forger`` button handler in 3_Forge.py (lines ~112-123) and the
# upgrade handler (lines ~197-206). Kept deliberately tiny so the behaviour —
# not the Streamlit plumbing — is what's verified.

def debiter_or_atomique(conn, joueur_id, cout):
    """Atomically debit ``cout`` gold from a player.

    Returns the debited row id on success, or ``None`` after rolling back when
    the balance is insufficient — exactly as the Forge handlers do before they
    insert/upgrade an item.
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE joueurs SET or_monnaie = or_monnaie - %s "
            "WHERE id = %s AND or_monnaie >= %s RETURNING id",
            (cout, joueur_id, cout),
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return None
        return row[0] if not isinstance(row, dict) else row["id"]


class TestAtomicDebit:
    def test_sufficient_funds_returns_id_and_does_not_rollback(self):
        cur = FakeCursor([("UPDATE joueurs", {"id": 7})])
        conn = FakeConn(cur)

        result = debiter_or_atomique(conn, joueur_id=7, cout=50)

        assert result == 7
        assert conn.rolledback == 0

    def test_insufficient_funds_returns_none_and_rolls_back(self):
        # The conditional UPDATE matched no row -> RETURNING yields nothing.
        cur = FakeCursor([("UPDATE joueurs", None)])
        conn = FakeConn(cur)

        result = debiter_or_atomique(conn, joueur_id=7, cout=999_999)

        assert result is None
        assert conn.rolledback == 1

    def test_debit_uses_guarded_conditional_update(self):
        cur = FakeCursor([("UPDATE joueurs", {"id": 7})])
        conn = FakeConn(cur)

        debiter_or_atomique(conn, joueur_id=7, cout=150)

        sql, params = cur.executed[0]
        # The WHERE clause must guard on the balance, and the amount must be
        # passed for both the subtraction and the guard (no TOCTOU race).
        assert "or_monnaie >= %s" in sql
        assert "RETURNING id" in sql
        assert params == (150, 7, 150)


class TestForgeSourceContract:
    """Guard tests: the production page must keep the atomic-debit guard.

    If someone replaces the conditional UPDATE with a plain subtraction, or
    drops the ``rollback()`` on the ``None`` branch, these fail loudly.
    """

    def test_forge_uses_atomic_conditional_update(self, forge_source):
        assert "or_monnaie = or_monnaie - %s" in forge_source
        assert "or_monnaie >= %s RETURNING id" in forge_source

    def test_forge_rolls_back_when_balance_insufficient(self, forge_source):
        # Every "fetchone() is None" guard in the file must roll back.
        guards = re.findall(
            r"if cur\.fetchone\(\) is None:(.*?)(?=\n\s*cur\.execute|\Z)",
            forge_source,
            re.DOTALL,
        )
        assert guards, "expected at least one insufficient-balance guard"
        for block in guards:
            assert "conn.rollback()" in block, (
                "an insufficient-balance guard does not roll back the transaction"
            )

    def test_forge_has_two_debit_sites(self, forge_source):
        # Forging an item and upgrading one are the two gold-spending paths.
        count = forge_source.count("or_monnaie >= %s RETURNING id")
        assert count == 2, (
            f"expected 2 atomic debit sites in the Forge page, found {count}"
        )
