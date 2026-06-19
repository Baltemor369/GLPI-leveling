"""Tests for ``sync/combat_engine.py``.

Two groups:

* Pure stat functions (``pv_max``, ``force_effective``, ``resistance_effective``,
  ``agilite_effective``, ``chance_esquive``) — exercised directly, no mocking.
* DB-backed functions (``accepter_combat``, ``jouer_action``) — the psycopg2
  connection and cursor are replaced by a programmable fake that routes each
  SQL statement to a canned result, so no real database is required.
"""

from unittest import mock

import pytest

import combat_engine as ce


# ── Helpers: fixtures de données ────────────────────────────────────────────

def make_joueur(**overrides):
    """A baseline player row (all stats present, as the DB would return)."""
    base = {
        "id": 1,
        "username": "Alice",
        "level": 4,
        "force_p": 10,
        "constitution_pv": 10,
        "agilite_vit": 10,
        "esprit_res": 10,
        "or_monnaie": 1000,
    }
    base.update(overrides)
    return base


# ── Fake cursor / connection ────────────────────────────────────────────────

class FakeCursor:
    """Minimal stand-in for a psycopg2 (RealDict) cursor.

    ``responses`` is a list of (matcher, result) pairs.  ``matcher`` is a
    substring searched (case-insensitively) in the executed SQL; the first
    matching, not-yet-consumed entry supplies the value returned by the next
    ``fetchone`` / ``fetchall``.  This lets a test describe exactly what each
    query in a function should "find" in the database.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self._pending = None
        self.executed = []  # (sql, params) log for assertions

    # context-manager protocol (``with conn.cursor() as cur``)
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        self._pending = None
        for i, (matcher, result) in enumerate(self._responses):
            if matcher.lower() in sql.lower():
                self._pending = result
                del self._responses[i]
                return
        # No canned answer => the query returns nothing.
        self._pending = None

    def fetchone(self):
        if isinstance(self._pending, list):
            return self._pending[0] if self._pending else None
        return self._pending

    def fetchall(self):
        if self._pending is None:
            return []
        return self._pending if isinstance(self._pending, list) else [self._pending]


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = 0
        self.rolledback = 0

    def cursor(self, *args, **kwargs):
        return self._cursor

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolledback += 1


# ═══════════════════════════════════════════════════════════════════════════
# Pure functions
# ═══════════════════════════════════════════════════════════════════════════

class TestPvMax:
    def test_base_without_equipment(self):
        # constitution 10 * 5 = 50
        assert ce.pv_max(make_joueur(constitution_pv=10), []) == 50

    def test_adds_constitution_equipment_bonus(self):
        eq = [{"type": "amul", "bonus_stat": "constitution_pv",
               "valeur_bonus": 8, "amelioration": 0}]
        # 10*5 + 8
        assert ce.pv_max(make_joueur(constitution_pv=10), eq) == 58

    def test_amelioration_counts_double(self):
        eq = [{"type": "amul", "bonus_stat": "constitution_pv",
               "valeur_bonus": 8, "amelioration": 3}]
        # 50 + (8 + 3*2) = 50 + 14
        assert ce.pv_max(make_joueur(constitution_pv=10), eq) == 64

    def test_transcendance_passive_adds_half_level_to_constitution(self):
        eq = [{"type": "amul", "bonus_stat": "constitution_pv", "valeur_bonus": 20,
               "amelioration": 0, "passif_code": "transcendance"}]
        # level 4 -> +2 constitution => (10+2)*5 + 20 = 80
        assert ce.pv_max(make_joueur(level=4, constitution_pv=10), eq) == 80


class TestForceEffective:
    def test_base(self):
        assert ce.force_effective(make_joueur(force_p=10), []) == 10

    def test_with_force_equipment(self):
        eq = [{"type": "arme", "bonus_stat": "force_p",
               "valeur_bonus": 12, "amelioration": 2}]
        # 10 + (12 + 2*2) = 26
        assert ce.force_effective(make_joueur(force_p=10), eq) == 26

    def test_transcendance_adds_half_level(self):
        eq = [{"type": "amul", "bonus_stat": "agilite_vit", "valeur_bonus": 0,
               "amelioration": 0, "passif_code": "transcendance"}]
        # level 6 -> +3 force => 10 + 3 = 13
        assert ce.force_effective(make_joueur(level=6, force_p=10), eq) == 13


class TestResistanceEffective:
    def test_base(self):
        assert ce.resistance_effective(make_joueur(esprit_res=10), []) == 10

    def test_with_resistance_equipment(self):
        eq = [{"type": "armure", "bonus_stat": "esprit_res",
               "valeur_bonus": 12, "amelioration": 0}]
        assert ce.resistance_effective(make_joueur(esprit_res=10), eq) == 22

    def test_bouclier_pv_passive_adds_5pct_of_pv_max(self):
        eq = [{"type": "armure", "bonus_stat": "esprit_res", "valeur_bonus": 22,
               "amelioration": 0, "passif_code": "bouclier_pv"}]
        joueur = make_joueur(esprit_res=10, constitution_pv=10)
        # pv_max = 10*5 + 0 (no constitution bonus item) = 50.
        # round(50 * 0.05) = round(2.5) = 2 (Python banker's rounding).
        # base res = 10 + 22 = 32, + 2 = 34
        assert ce.resistance_effective(joueur, eq) == 34


class TestAgiliteEffective:
    def test_base(self):
        assert ce.agilite_effective(make_joueur(agilite_vit=10), []) == 10

    def test_with_agility_equipment(self):
        eq = [{"type": "amul", "bonus_stat": "agilite_vit",
               "valeur_bonus": 6, "amelioration": 1}]
        # 10 + (6 + 1*2) = 18
        assert ce.agilite_effective(make_joueur(agilite_vit=10), eq) == 18


class TestChanceEsquive:
    def test_base_when_stats_equal(self):
        # 0.05 + (10 - 10)*0.01 = 0.05
        assert ce.chance_esquive(10, 10) == pytest.approx(0.05)

    def test_higher_agility_increases_dodge(self):
        # 0.05 + (20 - 10)*0.01 = 0.15
        assert ce.chance_esquive(20, 10) == pytest.approx(0.15)

    def test_floor_at_zero(self):
        # 0.05 + (0 - 100)*0.01 = -0.95 -> clamped to 0
        assert ce.chance_esquive(0, 100) == 0.0

    def test_cap_at_fifty_percent(self):
        # 0.05 + (100 - 0)*0.01 = 1.05 -> capped at 0.50
        assert ce.chance_esquive(100, 0) == 0.50

    def test_celerite_passive_adds_per_level(self):
        eq = [{"type": "amul", "bonus_stat": "agilite_vit", "valeur_bonus": 0,
               "amelioration": 0, "passif_code": "celerite_niveau"}]
        # base 0.05 + level 10 * 0.005 = 0.10
        assert ce.chance_esquive(10, 10, niveau_def=10, eq_def=eq) == pytest.approx(0.10)

    def test_celerite_passive_still_capped_at_fifty(self):
        eq = [{"type": "amul", "bonus_stat": "agilite_vit", "valeur_bonus": 0,
               "amelioration": 0, "passif_code": "celerite_niveau"}]
        assert ce.chance_esquive(100, 0, niveau_def=99, eq_def=eq) == 0.50


# ═══════════════════════════════════════════════════════════════════════════
# accepter_combat
# ═══════════════════════════════════════════════════════════════════════════

class TestAccepterCombat:
    def test_unauthorized_when_combat_not_found_for_player(self):
        # The guard SELECT filters on defenseur_id = joueur_id; if it returns
        # nothing the caller is not the defender (or the combat is gone).
        cur = FakeCursor([("FROM combats WHERE id", None)])
        conn = FakeConn(cur)

        result = ce.accepter_combat(conn, combat_id=42, joueur_id=999)

        assert result == "Accès non autorisé ou combat introuvable."
        assert conn.committed == 0

    def test_happy_path_without_stake_starts_combat(self):
        combat_row = {"id": 5, "attaquant_id": 1, "defenseur_id": 2, "mise": 0}
        att = make_joueur(id=1, username="Alice", agilite_vit=12)
        dfn = make_joueur(id=2, username="Bob", agilite_vit=8)
        cur = FakeCursor([
            ("FROM combats WHERE id", combat_row),
            ("FROM joueurs WHERE id", att),   # attaquant
            ("FROM joueurs WHERE id", dfn),   # defenseur
            ("FROM equipements", []),         # eq attaquant
            ("FROM equipements", []),         # eq defenseur
            ("UPDATE combats", None),
        ])
        conn = FakeConn(cur)

        result = ce.accepter_combat(conn, combat_id=5, joueur_id=2)

        assert result is None
        assert conn.committed == 1
        assert conn.rolledback == 0

    def test_attacker_insufficient_gold_rolls_back(self):
        combat_row = {"id": 5, "attaquant_id": 1, "defenseur_id": 2, "mise": 50}
        att = make_joueur(id=1, username="Alice", or_monnaie=10)
        dfn = make_joueur(id=2, username="Bob", or_monnaie=1000)
        cur = FakeCursor([
            ("FROM combats WHERE id", combat_row),
            ("FROM joueurs WHERE id", att),
            ("FROM joueurs WHERE id", dfn),
            ("FROM equipements", []),
            ("FROM equipements", []),
            # First debit (attacker) returns nothing => not enough gold.
            ("UPDATE joueurs", None),
        ])
        conn = FakeConn(cur)

        result = ce.accepter_combat(conn, combat_id=5, joueur_id=2)

        assert result == "L'attaquant n'a plus assez d'or pour la mise."
        assert conn.rolledback == 1
        assert conn.committed == 0

    def test_defender_insufficient_gold_rolls_back(self):
        combat_row = {"id": 5, "attaquant_id": 1, "defenseur_id": 2, "mise": 50}
        att = make_joueur(id=1, username="Alice", or_monnaie=1000)
        dfn = make_joueur(id=2, username="Bob", or_monnaie=10)
        cur = FakeCursor([
            ("FROM combats WHERE id", combat_row),
            ("FROM joueurs WHERE id", att),
            ("FROM joueurs WHERE id", dfn),
            ("FROM equipements", []),
            ("FROM equipements", []),
            # First debit (attacker) succeeds, second (defender) fails.
            ("UPDATE joueurs", {"id": 1}),
            ("UPDATE joueurs", None),
        ])
        conn = FakeConn(cur)

        result = ce.accepter_combat(conn, combat_id=5, joueur_id=2)

        assert result == "Tu n'as plus assez d'or pour cette mise."
        assert conn.rolledback == 1
        assert conn.committed == 0

    def test_both_stakes_debited_then_combat_started(self):
        combat_row = {"id": 5, "attaquant_id": 1, "defenseur_id": 2, "mise": 50}
        att = make_joueur(id=1, username="Alice", or_monnaie=1000)
        dfn = make_joueur(id=2, username="Bob", or_monnaie=1000)
        cur = FakeCursor([
            ("FROM combats WHERE id", combat_row),
            ("FROM joueurs WHERE id", att),
            ("FROM joueurs WHERE id", dfn),
            ("FROM equipements", []),
            ("FROM equipements", []),
            ("UPDATE joueurs", {"id": 1}),
            ("UPDATE joueurs", {"id": 2}),
            ("UPDATE combats", None),
        ])
        conn = FakeConn(cur)

        result = ce.accepter_combat(conn, combat_id=5, joueur_id=2)

        assert result is None
        assert conn.committed == 1
        assert conn.rolledback == 0


# ═══════════════════════════════════════════════════════════════════════════
# jouer_action
# ═══════════════════════════════════════════════════════════════════════════

class TestJouerActionGuards:
    def test_rejects_when_combat_not_active(self):
        combat = {
            "id": 1, "attaquant_id": 1, "defenseur_id": 2,
            "statut": "termine", "tour_de_qui": 1, "mise": 0,
            "pv_attaquant": 50, "pv_defenseur": 50, "log_combat": "",
        }
        cur = FakeCursor([("FROM combats WHERE id", combat)])
        conn = FakeConn(cur)

        result = ce.jouer_action(conn, 1, joueur_id=1, action_id="rapide")

        assert result == {"erreur": "Combat non actif."}
        assert conn.committed == 0

    def test_rejects_when_not_players_turn(self):
        combat = {
            "id": 1, "attaquant_id": 1, "defenseur_id": 2,
            "statut": "en_cours", "tour_de_qui": 1, "mise": 0,
            "pv_attaquant": 50, "pv_defenseur": 50, "log_combat": "",
        }
        cur = FakeCursor([("FROM combats WHERE id", combat)])
        conn = FakeConn(cur)

        # Player 2 tries to act while it is player 1's turn.
        result = ce.jouer_action(conn, 1, joueur_id=2, action_id="rapide")

        assert result == {"erreur": "Ce n'est pas ton tour."}
        assert conn.committed == 0


class TestJouerActionRepos:
    def test_repos_heals_15pct_of_pv_max(self):
        combat = {
            "id": 1, "attaquant_id": 1, "defenseur_id": 2,
            "statut": "en_cours", "tour_de_qui": 1, "mise": 0,
            "pv_attaquant": 20, "pv_defenseur": 50, "log_combat": "",
        }
        actor = make_joueur(id=1, username="Alice", constitution_pv=10)  # pv_max 50
        target = make_joueur(id=2, username="Bob", constitution_pv=10)
        cur = FakeCursor([
            ("FROM combats WHERE id", combat),
            ("FROM joueurs WHERE id", actor),    # _get_joueur(joueur_id)
            ("FROM joueurs WHERE id", target),   # _get_joueur(cible_id)
            ("FROM equipements", []),            # eq_att
            ("FROM equipements", []),            # eq_def
            ("UPDATE combats", None),
        ])
        conn = FakeConn(cur)

        result = ce.jouer_action(conn, 1, joueur_id=1, action_id="repos")

        # heal = int(50 * 0.15) = 7 ; 20 + 7 = 27, capped at pv_max 50
        assert result["degats"] == 0
        assert result["termine"] is False
        # The combat UPDATE should persist 27 PV for the attacker.
        update = [e for e in cur.executed if "UPDATE combats" in e[0]
                  and "statut=%s" in e[0]][0]
        params = update[1]
        # params order: (statut, prochain, new_pv_att, new_pv_def, log, id)
        assert params[2] == 27  # new_pv_att
        assert conn.committed == 1

    def test_repos_does_not_exceed_pv_max(self):
        combat = {
            "id": 1, "attaquant_id": 1, "defenseur_id": 2,
            "statut": "en_cours", "tour_de_qui": 1, "mise": 0,
            "pv_attaquant": 48, "pv_defenseur": 50, "log_combat": "",
        }
        actor = make_joueur(id=1, username="Alice", constitution_pv=10)  # pv_max 50
        target = make_joueur(id=2, username="Bob", constitution_pv=10)
        cur = FakeCursor([
            ("FROM combats WHERE id", combat),
            ("FROM joueurs WHERE id", actor),
            ("FROM joueurs WHERE id", target),
            ("FROM equipements", []),
            ("FROM equipements", []),
            ("UPDATE combats", None),
        ])
        conn = FakeConn(cur)

        ce.jouer_action(conn, 1, joueur_id=1, action_id="repos")

        update = [e for e in cur.executed if "UPDATE combats" in e[0]
                  and "statut=%s" in e[0]][0]
        # 48 + 7 = 55 but capped at 50
        assert update[1][2] == 50


class TestJouerActionDamage:
    def _run_attack(self, action_id, attacker, defender, pv_defenseur=50,
                    eq_att=None, eq_def=None, random_value=0.99):
        """Drive one offensive turn (attacker = player 1).

        ``random_value`` is patched into ``random.random`` so dodge / passive
        proc rolls are deterministic. 0.99 means "no dodge, no proc".
        """
        combat = {
            "id": 1, "attaquant_id": 1, "defenseur_id": 2,
            "statut": "en_cours", "tour_de_qui": 1, "mise": 0,
            "pv_attaquant": 50, "pv_defenseur": pv_defenseur, "log_combat": "",
        }
        cur = FakeCursor([
            ("FROM combats WHERE id", combat),
            ("FROM joueurs WHERE id", attacker),
            ("FROM joueurs WHERE id", defender),
            ("FROM equipements", eq_att or []),
            ("FROM equipements", eq_def or []),
            ("UPDATE combats", None),
            ("UPDATE joueurs", None),   # victory gold gain (if combat ends)
            ("FROM joueurs WHERE id", attacker),  # _get_joueur(vainqueur) on win
            ("UPDATE combats", None),   # log + vainqueur_id on win
        ])
        conn = FakeConn(cur)
        # ``jouer_action`` does ``import random`` internally, so we patch the
        # global ``random.random``. Badge checking hits the DB on victory;
        # stub it out (returns no badge).
        with mock.patch("random.random", return_value=random_value), \
                mock.patch.object(ce.badge_engine, "verifier_badges_combat",
                                  return_value=[]):
            result = ce.jouer_action(conn, 1, joueur_id=1, action_id=action_id)
        return result, cur, conn

    def test_basic_damage_formula(self):
        # force 20, multiplier 1.0, resistance 5 => 20*1 - 5 = 15 damage
        attacker = make_joueur(id=1, username="Alice", force_p=20)
        defender = make_joueur(id=2, username="Bob", esprit_res=5)
        result, _, _ = self._run_attack("rapide", attacker, defender)

        assert result["degats"] == 15
        assert result["pv_restants"] == 35  # 50 - 15
        assert result["termine"] is False

    def test_heavy_strike_uses_multiplier(self):
        # force 20, "lourde" multiplier 1.8 => int(20*1.8) - 0 res = 36
        attacker = make_joueur(id=1, username="Alice", force_p=20)
        defender = make_joueur(id=2, username="Bob", esprit_res=0)
        result, _, _ = self._run_attack("lourde", attacker, defender)

        assert result["degats"] == 36
        assert result["pv_restants"] == 14  # 50 - 36

    def test_damage_has_floor_of_one(self):
        # tiny force, huge resistance => formula would be negative, floored to 1
        attacker = make_joueur(id=1, username="Alice", force_p=1)
        defender = make_joueur(id=2, username="Bob", esprit_res=100)
        result, _, _ = self._run_attack("rapide", attacker, defender)

        assert result["degats"] == 1

    def test_dodge_deals_no_damage(self):
        # High defender agility vs low attacker force => non-zero dodge chance.
        # chance_esquive(100, 20) = 0.05 + (100-20)*0.01 -> capped at 0.50.
        attacker = make_joueur(id=1, username="Alice", force_p=20)
        defender = make_joueur(id=2, username="Bob", esprit_res=0, agilite_vit=100)
        # random=0.0 < 0.50 forces the dodge branch.
        result, _, _ = self._run_attack("rapide", attacker, defender,
                                        random_value=0.0)

        assert result["degats"] == 0
        assert result["pv_restants"] == 50  # untouched

    def test_lethal_hit_ends_combat_and_awards_gold(self):
        # force 100 kills the 50-PV defender outright.
        attacker = make_joueur(id=1, username="Alice", force_p=100)
        defender = make_joueur(id=2, username="Bob", esprit_res=0)
        result, cur, conn = self._run_attack("rapide", attacker, defender,
                                             pv_defenseur=50)

        assert result["termine"] is True
        assert result["pv_restants"] == 0
        # Winner must be credited with gold (mise*2 + OR_VICTOIRE_BASE).
        gold_update = [e for e in cur.executed
                       if "or_monnaie = or_monnaie + %s" in e[0]]
        assert gold_update, "winner should receive a gold reward"
        assert gold_update[0][1][0] == ce.OR_VICTOIRE_BASE  # mise 0 -> base only
        assert conn.committed == 1
