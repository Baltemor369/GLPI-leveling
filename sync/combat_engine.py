"""
Moteur de combat PvP au tour par tour.
State machine : en_attente → en_cours → termine
"""

import psycopg2.extras
import badge_engine

OR_VICTOIRE_BASE = 10  # récompense minimale même à mise 0

# Actions disponibles : (id, label, multiplicateur, description, malus_vitesse)
# malus_vitesse réduit la force effective de l'attaquant dans le calcul d'esquive :
# une attaque lente est plus facile à esquiver même si elle fait plus de dégâts.
ACTIONS = [
    ("rapide",   "Attaque Rapide",   1.0,  "Coup sûr — vitesse pleine",          0.00),
    ("lourde",   "Frappe Lourde",    1.8,  "Dégâts élevés — frappe plus lente",  0.20),
    ("critique", "Coup Critique",    2.5,  "Dégâts massifs — coup très lent",    0.40),
    ("repos",    "Repos",            0.0,  "Récupère 15% des PV max",            0.00),
]
ACTIONS_MAP = {a[0]: a for a in ACTIONS}


def _get_joueur(cur, joueur_id):
    cur.execute("SELECT * FROM joueurs WHERE id = %s", (joueur_id,))
    return dict(cur.fetchone())


def _get_equipements(cur, joueur_id):
    cur.execute("SELECT * FROM equipements WHERE joueur_id = %s AND equipe = TRUE", (joueur_id,))
    return [dict(r) for r in cur.fetchall()]


def pv_max(joueur: dict, equipements: list) -> int:
    """PV max = constitution × 5 + bonus armure constitution."""
    base = joueur["constitution_pv"] * 5
    bonus = sum(e["valeur_bonus"] for e in equipements if e["bonus_stat"] == "constitution_pv")
    return base + bonus


def force_effective(joueur: dict, equipements: list) -> int:
    return joueur["force_p"] + sum(
        e["valeur_bonus"] for e in equipements if e["bonus_stat"] == "force_p"
    )


def resistance_effective(joueur: dict, equipements: list) -> int:
    return joueur["esprit_res"] + sum(
        e["valeur_bonus"] for e in equipements if e["bonus_stat"] == "esprit_res"
    )


def agilite_effective(joueur: dict, equipements: list) -> int:
    return joueur["agilite_vit"] + sum(
        e["valeur_bonus"] for e in equipements if e["bonus_stat"] == "agilite_vit"
    )


def chance_esquive(agilite_def: int, force_att: int) -> float:
    """5% de base + 1% par point d'agilité du défenseur − 1% par point de force de l'attaquant.
    La force de l'attaquant rend sa frappe plus rapide, donc plus difficile à esquiver.
    Plafonnée à 50%, plancher à 0%.
    """
    return max(0.0, min(0.50, 0.05 + (agilite_def - force_att) * 0.01))


def creer_combat(conn, attaquant_id: int, defenseur_id: int, mise: int = 0) -> int:
    """Crée un combat en_attente avec la mise fixée par l'attaquant."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO combats (attaquant_id, defenseur_id, statut, mise)
            VALUES (%s, %s, 'en_attente', %s) RETURNING id
        """, (attaquant_id, defenseur_id, max(0, mise)))
        combat_id = cur.fetchone()[0]
    conn.commit()
    return combat_id


def accepter_combat(conn, combat_id: int):
    """Le défenseur accepte → calcul initiative → passage en en_cours."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM combats WHERE id = %s", (combat_id,))
        combat = dict(cur.fetchone())

        att  = _get_joueur(cur, combat["attaquant_id"])
        dfn  = _get_joueur(cur, combat["defenseur_id"])
        eq_a = _get_equipements(cur, att["id"])
        eq_d = _get_equipements(cur, dfn["id"])

        pv_a = pv_max(att, eq_a)
        pv_d = pv_max(dfn, eq_d)

        # Initiative : le plus agile attaque en premier (égalité → attaquant)
        agi_a = agilite_effective(att, eq_a)
        agi_d = agilite_effective(dfn, eq_d)
        premier = att["id"] if agi_a >= agi_d else dfn["id"]

        mise = combat["mise"]
        # Débiter la mise des deux joueurs
        if mise > 0:
            cur.execute("UPDATE joueurs SET or_monnaie = or_monnaie - %s WHERE id = %s", (mise, att["id"]))
            cur.execute("UPDATE joueurs SET or_monnaie = or_monnaie - %s WHERE id = %s", (mise, dfn["id"]))

        mise_info = f" | Mise : {mise} or chacun (pot : {mise * 2} or)" if mise > 0 else ""
        log = (f"Combat commencé ! Initiative : {att['username'] if premier == att['id'] else dfn['username']} "
               f"(AGI {max(agi_a, agi_d)} vs {min(agi_a, agi_d)}){mise_info}\n")

        cur.execute("""
            UPDATE combats
            SET statut='en_cours', tour_de_qui=%s,
                pv_attaquant=%s, pv_defenseur=%s,
                log_combat=%s
            WHERE id=%s
        """, (premier, pv_a, pv_d, log, combat_id))
    conn.commit()


def jouer_action(conn, combat_id: int, joueur_id: int, action_id: str) -> dict:
    """
    Joue une action pour joueur_id dans le combat.
    Retourne un dict avec le résultat du tour.
    """
    import random

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM combats WHERE id = %s FOR UPDATE", (combat_id,))
        combat = dict(cur.fetchone())

        if combat["statut"] != "en_cours":
            return {"erreur": "Combat non actif."}
        if combat["tour_de_qui"] != joueur_id:
            return {"erreur": "Ce n'est pas ton tour."}

        att_id = combat["attaquant_id"]
        dfn_id = combat["defenseur_id"]
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

        degats = 0
        log_ligne = f"  {attaqueur['username']} → {label}"

        if action_id == "repos":
            soin = max(1, int(pv_max(attaqueur, eq_att) * 0.15))
            pv_att_now = min(pv_max(attaqueur, eq_att), pv_att_now + soin)
            log_ligne += f" (+{soin} PV récupérés)"
        else:
            force        = force_effective(attaqueur, eq_att)
            force_rapide = force * (1 - malus_vitesse)  # force réduite selon vitesse de l'attaque
            agi_def      = agilite_effective(cible, eq_def)
            esquive      = chance_esquive(agi_def, force_rapide)
            if random.random() < esquive:
                log_ligne += f" — ESQUIVÉ ! ({cible['username']} : {pv_def_now} PV)"
            else:
                res    = resistance_effective(cible, eq_def)
                degats = max(1, int(force * multiplicateur) - res)
                pv_def_now = max(0, pv_def_now - degats)
                log_ligne += f" — {degats} dégâts ! ({cible['username']} : {pv_def_now} PV)"

        # Prochain tour
        prochain = cible_id if pv_def_now > 0 else None
        nouveau_statut = "en_cours" if pv_def_now > 0 else "termine"
        nouveau_log = combat["log_combat"] + log_ligne + "\n"

        new_pv_att = pv_att_now if est_attaquant else pv_def_now
        new_pv_def = pv_def_now if est_attaquant else pv_att_now

        cur.execute("""
            UPDATE combats
            SET statut=%s, tour_de_qui=%s,
                pv_attaquant=%s, pv_defenseur=%s,
                log_combat=%s
            WHERE id=%s
        """, (nouveau_statut, prochain, new_pv_att, new_pv_def, nouveau_log, combat_id))

        if nouveau_statut == "termine":
            vainqueur_id = joueur_id
            vainqueur    = _get_joueur(cur, vainqueur_id)
            gain = combat["mise"] * 2 + OR_VICTOIRE_BASE
            cur.execute(
                "UPDATE joueurs SET or_monnaie = or_monnaie + %s WHERE id = %s",
                (gain, vainqueur_id),
            )
            cur.execute(
                "UPDATE combats SET log_combat = log_combat || %s, vainqueur_id = %s WHERE id = %s",
                (f"\nVICTOIRE de {vainqueur['username']} ! (+{gain} or)\n", vainqueur_id, combat_id),
            )

    conn.commit()

    nouveaux_badges = []
    if nouveau_statut == "termine":
        nouveaux_badges = badge_engine.verifier_badges_combat(
            conn,
            vainqueur_id   = joueur_id,
            mise           = combat["mise"],
            action_gagnante = action_id,
            log_combat     = nouveau_log,
            username_vainqueur = attaqueur["username"],
        )

    return {
        "degats":          degats,
        "pv_restants":     pv_def_now,
        "termine":         nouveau_statut == "termine",
        "nouveaux_badges": nouveaux_badges,
    }


def get_combat(conn, combat_id: int) -> dict | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM combats WHERE id = %s", (combat_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_combats_joueur(conn, joueur_id: int) -> list:
    """Retourne les combats en attente ou en cours impliquant ce joueur."""
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
