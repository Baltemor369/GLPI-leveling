"""
Moteur de combat PvP au tour par tour.
State machine : en_attente → en_cours → termine
"""

import psycopg2.extras
import badge_engine

OR_VICTOIRE_BASE = 10
ELO_K            = 32


def _elo_delta(pc_vainqueur: int, pc_perdant: int) -> int:
    """PC gagnés par le vainqueur (formule Elo K=32). Minimum 1."""
    expected = 1 / (1 + 10 ** ((pc_perdant - pc_vainqueur) / 400))
    return max(1, round(ELO_K * (1 - expected)))

# Actions disponibles : (id, label, multiplicateur, description, malus_vitesse)
ACTIONS = [
    ("rapide",   "Attaque Rapide",   1.0,  "Coup sûr — vitesse pleine",          0.00),
    ("lourde",   "Frappe Lourde",    1.8,  "Dégâts élevés — frappe plus lente",  0.20),
    ("critique", "Coup Critique",    2.5,  "Dégâts massifs — coup très lent",    0.40),
    ("repos",    "Repos",            0.0,  "Récupère 15% des PV max",            0.00),
]
ACTIONS_MAP = {a[0]: a for a in ACTIONS}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_joueur(cur, joueur_id):
    cur.execute("SELECT * FROM joueurs WHERE id = %s", (joueur_id,))
    return dict(cur.fetchone())


def _get_equipements(cur, joueur_id):
    cur.execute("SELECT * FROM equipements WHERE joueur_id = %s AND equipe = TRUE", (joueur_id,))
    return [dict(r) for r in cur.fetchall()]


def _passif(equipements: list, type_item: str) -> str | None:
    """Retourne le passif_code de l'item équipé du type donné, ou None."""
    for e in equipements:
        if e["type"] == type_item:
            return e.get("passif_code")
    return None


def _bonus_eq(equipements: list, bonus_stat: str) -> int:
    """Somme valeur_bonus + amelioration*2 pour tous les items d'un stat donné."""
    return sum(
        e["valeur_bonus"] + e.get("amelioration", 0) * 2
        for e in equipements if e["bonus_stat"] == bonus_stat
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

def pv_max(joueur: dict, equipements: list) -> int:
    transcendance = joueur["level"] // 2 if _passif(equipements, "amul") == "transcendance" else 0
    constitution  = joueur["constitution_pv"] + transcendance
    return constitution * 5 + _bonus_eq(equipements, "constitution_pv")


def force_effective(joueur: dict, equipements: list) -> int:
    transcendance = joueur["level"] // 2 if _passif(equipements, "amul") == "transcendance" else 0
    return joueur["force_p"] + transcendance + _bonus_eq(equipements, "force_p")


def resistance_effective(joueur: dict, equipements: list) -> int:
    transcendance = joueur["level"] // 2 if _passif(equipements, "amul") == "transcendance" else 0
    base = joueur["esprit_res"] + transcendance + _bonus_eq(equipements, "esprit_res")
    # Armure de Plates (T3) : +5% de résistance basée sur les PV max
    if _passif(equipements, "armure") == "bouclier_pv":
        base += round(pv_max(joueur, equipements) * 0.05)
    return base


def agilite_effective(joueur: dict, equipements: list) -> int:
    transcendance = joueur["level"] // 2 if _passif(equipements, "amul") == "transcendance" else 0
    return joueur["agilite_vit"] + transcendance + _bonus_eq(equipements, "agilite_vit")


def chance_esquive(agilite_def: int, force_att: float,
                   niveau_def: int = 0, eq_def: list = None) -> float:
    """5% + 1%/pt AGI défenseur − 1%/pt force attaquant.
    Talisman Runique : +0.5% par niveau de personnage. Plafond 50%.
    """
    base = max(0.0, min(0.50, 0.05 + (agilite_def - force_att) * 0.01))
    if eq_def and _passif(eq_def, "amul") == "celerite_niveau":
        base = min(0.50, base + niveau_def * 0.005)
    return base


# ── Création / Acceptation ────────────────────────────────────────────────────

def creer_combat(conn, attaquant_id: int, defenseur_id: int, mise: int = 0) -> int:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO combats (attaquant_id, defenseur_id, statut, mise)
            VALUES (%s, %s, 'en_attente', %s) RETURNING id
        """, (attaquant_id, defenseur_id, max(0, mise)))
        combat_id = cur.fetchone()[0]
    conn.commit()
    return combat_id


def accepter_combat(conn, combat_id: int, joueur_id: int) -> str | None:
    """Accepte le combat. Retourne None si OK, message d'erreur sinon."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM combats WHERE id = %s AND defenseur_id = %s AND statut = 'en_attente'",
            (combat_id, joueur_id),
        )
        combat_row = cur.fetchone()
        if not combat_row:
            return "Accès non autorisé ou combat introuvable."
        combat = dict(combat_row)

        att  = _get_joueur(cur, combat["attaquant_id"])
        dfn  = _get_joueur(cur, combat["defenseur_id"])
        eq_a = _get_equipements(cur, att["id"])
        eq_d = _get_equipements(cur, dfn["id"])

        pv_a   = pv_max(att, eq_a)
        pv_d   = pv_max(dfn, eq_d)
        agi_a  = agilite_effective(att, eq_a)
        agi_d  = agilite_effective(dfn, eq_d)
        premier = att["id"] if agi_a >= agi_d else dfn["id"]

        mise = combat["mise"]
        if mise > 0:
            cur.execute(
                "UPDATE joueurs SET or_monnaie = or_monnaie - %s "
                "WHERE id = %s AND or_monnaie >= %s RETURNING id",
                (mise, att["id"], mise),
            )
            if cur.fetchone() is None:
                conn.rollback()
                return "L'attaquant n'a plus assez d'or pour la mise."
            cur.execute(
                "UPDATE joueurs SET or_monnaie = or_monnaie - %s "
                "WHERE id = %s AND or_monnaie >= %s RETURNING id",
                (mise, dfn["id"], mise),
            )
            if cur.fetchone() is None:
                conn.rollback()
                return "Tu n'as plus assez d'or pour cette mise."

        mise_info = f" | Mise : {mise} or chacun (pot : {mise * 2} or)" if mise > 0 else ""
        log = (f"Combat commencé ! Initiative : "
               f"{att['username'] if premier == att['id'] else dfn['username']} "
               f"(AGI {max(agi_a, agi_d)} vs {min(agi_a, agi_d)}){mise_info}\n")

        cur.execute("""
            UPDATE combats
            SET statut='en_cours', tour_de_qui=%s,
                pv_attaquant=%s, pv_defenseur=%s, log_combat=%s
            WHERE id=%s
        """, (premier, pv_a, pv_d, log, combat_id))
    conn.commit()
    return None


# ── Tour de jeu ───────────────────────────────────────────────────────────────

def jouer_action(conn, combat_id: int, joueur_id: int, action_id: str) -> dict:
    import random

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM combats WHERE id = %s FOR UPDATE", (combat_id,))
        combat = dict(cur.fetchone())

        if combat["statut"] != "en_cours":
            return {"erreur": "Combat non actif."}
        if combat["tour_de_qui"] != joueur_id:
            return {"erreur": "Ce n'est pas ton tour."}

        att_id        = combat["attaquant_id"]
        dfn_id        = combat["defenseur_id"]
        est_attaquant = (joueur_id == att_id)

        attaqueur = _get_joueur(cur, joueur_id)
        cible_id  = dfn_id if est_attaquant else att_id
        cible     = _get_joueur(cur, cible_id)
        eq_att    = _get_equipements(cur, joueur_id)
        eq_def    = _get_equipements(cur, cible_id)

        pv_att_col = "pv_attaquant" if est_attaquant else "pv_defenseur"
        pv_def_col = "pv_defenseur" if est_attaquant else "pv_attaquant"
        pv_att_now = combat[pv_att_col]
        pv_def_now = combat[pv_def_col]

        action = ACTIONS_MAP.get(action_id, ACTIONS_MAP["rapide"])
        _, label, multiplicateur, _, malus_vitesse = action

        degats     = 0
        delta_pc   = 0
        extra_logs = []

        # ── Auto-heal (SSD NVMe T3) — début de tour ──────────────────────────
        if _passif(eq_att, "amul") == "regeneration":
            regen = max(1, round(pv_max(attaqueur, eq_att) * 0.05))
            pv_att_now = min(pv_max(attaqueur, eq_att), pv_att_now + regen)
            extra_logs.append(f"  ↺ {attaqueur['username']} Auto-heal (+{regen} PV)")

        log_ligne = f"  {attaqueur['username']} → {label}"

        if action_id == "repos":
            soin = max(1, int(pv_max(attaqueur, eq_att) * 0.15))
            pv_att_now = min(pv_max(attaqueur, eq_att), pv_att_now + soin)
            log_ligne += f" (+{soin} PV récupérés)"

        else:
            force        = force_effective(attaqueur, eq_att)
            force_rapide = force * (1 - malus_vitesse)
            agi_def      = agilite_effective(cible, eq_def)
            esquive      = chance_esquive(agi_def, force_rapide, cible["level"], eq_def)

            if random.random() < esquive:
                log_ligne += f" — ESQUIVÉ ! ({cible['username']} : {pv_def_now} PV)"

            else:
                # ── Air Gap (Zero Trust T5) ──────────────────────────────────
                if _passif(eq_def, "armure") == "immunite" and random.random() < 0.25:
                    log_ligne += f" — AIR GAP ! ({cible['username']} : {pv_def_now} PV)"

                else:
                    res    = resistance_effective(cible, eq_def)
                    degats = max(1, int(force * multiplicateur) - res)

                    # ── Kill Process (CPU Quantique T5) ──────────────────────
                    if _passif(eq_att, "arme") == "execution":
                        if pv_def_now < pv_max(cible, eq_def) * 0.20:
                            degats = round(degats * 1.5)
                            log_ligne += " [💀Kill Process]"

                    # ── Overclock (Core i5 T3) ───────────────────────────────
                    if _passif(eq_att, "arme") == "saignement" and random.random() < 0.20:
                        degats += 3
                        log_ligne += " [⚡Overclock]"

                    pv_def_now = max(0, pv_def_now - degats)
                    log_ligne += f" — {degats} dégâts ! ({cible['username']} : {pv_def_now} PV)"

                    # ── Cache Hit (Core i7 T4) ────────────────────────────────
                    if _passif(eq_att, "arme") == "vampirisme" and degats > 0:
                        soin_vamp = max(1, round(degats * 0.25))
                        pv_att_now = min(pv_max(attaqueur, eq_att), pv_att_now + soin_vamp)
                        log_ligne += f" [💾+{soin_vamp} PV]"

                    # ── Honeypot (IDS/IPS T4) ─────────────────────────────────
                    if _passif(eq_def, "armure") == "epines" and degats > 0:
                        reflet = max(1, round(degats * 0.15))
                        pv_att_now = max(0, pv_att_now - reflet)
                        log_ligne += f" [🔥Honeypot -{reflet}]"

        # ── Construire le log final ───────────────────────────────────────────
        nouveau_log = combat["log_combat"]
        for l in extra_logs:
            nouveau_log += l + "\n"
        nouveau_log += log_ligne + "\n"

        # ── Déterminer le vainqueur ───────────────────────────────────────────
        if pv_def_now <= 0:
            nouveau_statut = "termine"
            vainqueur_id   = joueur_id
            perdant_id     = cible_id
        elif pv_att_now <= 0:
            nouveau_statut = "termine"
            vainqueur_id   = cible_id
            perdant_id     = joueur_id
        else:
            nouveau_statut = "en_cours"
            vainqueur_id   = None
            perdant_id     = None

        prochain = cible_id if nouveau_statut == "en_cours" else None

        new_pv_att = pv_att_now if est_attaquant else pv_def_now
        new_pv_def = pv_def_now if est_attaquant else pv_att_now

        cur.execute("""
            UPDATE combats
            SET statut=%s, tour_de_qui=%s,
                pv_attaquant=%s, pv_defenseur=%s, log_combat=%s
            WHERE id=%s
        """, (nouveau_statut, prochain, new_pv_att, new_pv_def, nouveau_log, combat_id))

        if nouveau_statut == "termine":
            # Refetch avant tout UPDATE points_combat — valeurs Elo pré-combat requises
            vainqueur    = _get_joueur(cur, vainqueur_id)
            perdant_data = cible if vainqueur_id == joueur_id else attaqueur

            # Or victoire
            gain = combat["mise"] * 2 + OR_VICTOIRE_BASE
            cur.execute(
                "UPDATE joueurs SET or_monnaie = or_monnaie + %s WHERE id = %s",
                (gain, vainqueur_id),
            )

            # Points de Combat (Elo)
            delta_pc = _elo_delta(vainqueur["points_combat"], perdant_data["points_combat"])
            cur.execute(
                "UPDATE joueurs SET points_combat = points_combat + %s WHERE id = %s",
                (delta_pc, vainqueur_id),
            )
            cur.execute(
                "UPDATE joueurs SET points_combat = GREATEST(0, points_combat - %s) WHERE id = %s",
                (delta_pc, perdant_id),
            )

            cur.execute(
                "UPDATE combats SET log_combat = log_combat || %s, vainqueur_id = %s WHERE id = %s",
                (
                    f"\nVICTOIRE de {vainqueur['username']} ! (+{gain} or, +{delta_pc} PC)\n",
                    vainqueur_id,
                    combat_id,
                ),
            )

    conn.commit()

    nouveaux_badges = []
    if nouveau_statut == "termine":
        # L'action gagnante est celle du vainqueur : action_id si c'est joueur_id qui gagne
        action_gagnante = action_id if vainqueur_id == joueur_id else "?"
        nouveaux_badges = badge_engine.verifier_badges_combat(
            conn,
            vainqueur_id       = vainqueur_id,
            mise               = combat["mise"],
            action_gagnante    = action_gagnante,
            log_combat         = nouveau_log,
            username_vainqueur = vainqueur["username"],
        )

    return {
        "degats":          degats,
        "pv_restants":     pv_def_now,
        "termine":         nouveau_statut == "termine",
        "nouveaux_badges": nouveaux_badges,
        "delta_pc":        delta_pc,
    }


def get_combat(conn, combat_id: int) -> dict | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM combats WHERE id = %s", (combat_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_combats_joueur(conn, joueur_id: int) -> list:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT c.*,
                   ja.username AS nom_attaquant,
                   jd.username AS nom_defenseur
            FROM combats c
            JOIN joueurs ja ON ja.id = c.attaquant_id
            JOIN joueurs jd ON jd.id = c.defenseur_id
            WHERE (c.attaquant_id = %s OR c.defenseur_id = %s)
              AND c.statut != 'termine'
            ORDER BY c.id DESC
        """, (joueur_id, joueur_id))
        return [dict(r) for r in cur.fetchall()]
