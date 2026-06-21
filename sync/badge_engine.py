"""Vérification et attribution des badges après chaque événement déclencheur."""

from datetime import datetime
import db


def _count_tickets(conn, joueur_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tickets_traites WHERE joueur_id = %s", (joueur_id,))
        return cur.fetchone()[0]


def _count_tickets_serveur(conn, joueur_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM tickets_traites WHERE joueur_id = %s AND nom_categorie ILIKE %s",
            (joueur_id, "%serveur%"),
        )
        return cur.fetchone()[0]


def _count_tickets_conformes(conn, createur_id: int, seuil: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM tickets_traites WHERE createur_id = %s AND score_conformite >= %s",
            (createur_id, seuil),
        )
        return cur.fetchone()[0]


def _count_victoires(conn, joueur_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM combats WHERE vainqueur_id = %s AND statut = 'termine'",
            (joueur_id,),
        )
        return cur.fetchone()[0]


def verifier_badges_ticket(conn, joueur_id: int, nom_categorie: str,
                            date_creation: str, date_cloture: str) -> list:
    """Badges déclenchés après résolution d'un ticket."""
    nouveaux = []

    count = _count_tickets(conn, joueur_id)
    for code, seuil in [("premiere_quete", 1), ("ecuyer", 10), ("chevalier", 50), ("paladin", 100)]:
        if count >= seuil and db.attribuer_badge(conn, joueur_id, code):
            nouveaux.append(code)

    try:
        d_open  = datetime.fromisoformat(date_creation)
        d_close = datetime.fromisoformat(date_cloture)
        if d_open.date() == d_close.date():
            if db.attribuer_badge(conn, joueur_id, "eclair"):
                nouveaux.append("eclair")
    except Exception:
        pass

    if "serveur" in (nom_categorie or "").lower():
        if _count_tickets_serveur(conn, joueur_id) >= 10:
            if db.attribuer_badge(conn, joueur_id, "maitre_serveurs"):
                nouveaux.append("maitre_serveurs")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM tickets_traites
            WHERE joueur_id = %s AND date_traitement::date = CURRENT_DATE
        """, (joueur_id,))
        if cur.fetchone()[0] >= 5 and db.attribuer_badge(conn, joueur_id, "stakhanoviste"):
            nouveaux.append("stakhanoviste")

    return nouveaux


def verifier_badges_conformite(conn, createur_id: int | None, score_conformite: int) -> list:
    """Badges déclenchés après évaluation de la conformité d'un ticket."""
    if not createur_id:
        return []
    nouveaux = []
    if score_conformite == 10 and db.attribuer_badge(conn, createur_id, "plume_or"):
        nouveaux.append("plume_or")
    if _count_tickets_conformes(conn, createur_id, 8) >= 10:
        if db.attribuer_badge(conn, createur_id, "scribe_parfait"):
            nouveaux.append("scribe_parfait")
    return nouveaux


def verifier_badges_combat(conn, vainqueur_id: int, mise: int,
                            action_gagnante: str, log_combat: str,
                            username_vainqueur: str) -> list:
    """Badges déclenchés après une victoire en Arène."""
    nouveaux = []

    wins = _count_victoires(conn, vainqueur_id)
    for code, seuil in [("bapteme_feu", 1), ("gladiateur", 5), ("champion_arene", 10)]:
        if wins >= seuil and db.attribuer_badge(conn, vainqueur_id, code):
            nouveaux.append(code)

    esquives = log_combat.count(f"ESQUIVÉ ! ({username_vainqueur}")
    if esquives >= 3 and db.attribuer_badge(conn, vainqueur_id, "insaisissable"):
        nouveaux.append("insaisissable")

    if action_gagnante == "critique" and db.attribuer_badge(conn, vainqueur_id, "coup_de_grace"):
        nouveaux.append("coup_de_grace")

    if mise > 0 and db.attribuer_badge(conn, vainqueur_id, "parieur"):
        nouveaux.append("parieur")
    if mise >= 50 and db.attribuer_badge(conn, vainqueur_id, "haut_risque"):
        nouveaux.append("haut_risque")

    # 3 victoires consécutives
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT vainqueur_id FROM combats
                WHERE (attaquant_id = %s OR defenseur_id = %s) AND statut = 'termine'
                ORDER BY id DESC LIMIT 3
            ) sub WHERE vainqueur_id = %s
        """, (vainqueur_id, vainqueur_id, vainqueur_id))
        if cur.fetchone()[0] == 3 and db.attribuer_badge(conn, vainqueur_id, "invaincu"):
            nouveaux.append("invaincu")

    # Gagner sans avoir utilisé Repos
    if f"{username_vainqueur} → Repos" not in log_combat:
        if db.attribuer_badge(conn, vainqueur_id, "sans_pitie"):
            nouveaux.append("sans_pitie")

    return nouveaux


def verifier_badges_niveau(conn, joueur_id: int, nouveau_niveau: int) -> list:
    """Badges déclenchés après une montée de niveau."""
    nouveaux = []
    for code, seuil in [("ascension", 5), ("seigneur", 10), ("legende", 15)]:
        if nouveau_niveau >= seuil and db.attribuer_badge(conn, joueur_id, code):
            nouveaux.append(code)
    return nouveaux


def verifier_badges_forge(conn, joueur_id: int) -> list:
    """Badges déclenchés après une action en Forge (forger ou équiper)."""
    nouveaux = []

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM equipements WHERE joueur_id = %s", (joueur_id,))
        if cur.fetchone()[0] >= 1 and db.attribuer_badge(conn, joueur_id, "forgeron"):
            nouveaux.append("forgeron")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT type) FROM equipements
            WHERE joueur_id = %s AND equipe = TRUE AND type IN ('arme','armure','amul')
        """, (joueur_id,))
        if cur.fetchone()[0] == 3 and db.attribuer_badge(conn, joueur_id, "arsenal_complet"):
            nouveaux.append("arsenal_complet")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM equipements WHERE joueur_id = %s AND amelioration >= 5",
            (joueur_id,),
        )
        if cur.fetchone()[0] >= 1 and db.attribuer_badge(conn, joueur_id, "artisan"):
            nouveaux.append("artisan")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM equipements WHERE joueur_id = %s AND tier = 5",
            (joueur_id,),
        )
        if cur.fetchone()[0] >= 1 and db.attribuer_badge(conn, joueur_id, "grand_maitre_forge"):
            nouveaux.append("grand_maitre_forge")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT type) FROM equipements
            WHERE joueur_id = %s AND equipe = TRUE AND tier = 5
              AND type IN ('arme','armure','amul')
        """, (joueur_id,))
        if cur.fetchone()[0] == 3 and db.attribuer_badge(conn, joueur_id, "set_legendaire"):
            nouveaux.append("set_legendaire")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT type) FROM equipements
            WHERE joueur_id = %s AND equipe = TRUE AND tier = 5
              AND amelioration >= 20 AND type IN ('arme','armure','amul')
        """, (joueur_id,))
        if cur.fetchone()[0] == 3 and db.attribuer_badge(conn, joueur_id, "perfection_absolue"):
            nouveaux.append("perfection_absolue")

    return nouveaux


def verifier_badges_saison(conn, archives: list[dict]) -> dict[int, list[str]]:
    """Attribue les badges de fin de saison selon les classements finaux.
    Retourne {joueur_id: [codes_attribués]}.

    NOTE : en production, les badges saison sont attribués à l'intérieur de la
    transaction unique de ``archiver_et_reset_saison`` (db.py), pas via cette
    fonction. Cette fonction existe pour les tests unitaires qui vérifient la
    logique d'attribution de manière isolée, sans déclencher un reset complet.
    """
    resultats: dict[int, list[str]] = {}
    for r in archives:
        joueur_id = r["joueur_id"]
        nouveaux = []
        if r["rang_xp"] == 1 and db.attribuer_badge(conn, joueur_id, "saison_champion_xp"):
            nouveaux.append("saison_champion_xp")
        if r["rang_pc"] == 1 and db.attribuer_badge(conn, joueur_id, "saison_champion_pc"):
            nouveaux.append("saison_champion_pc")
        if (r["rang_xp"] <= 3 or r["rang_pc"] <= 3) and db.attribuer_badge(conn, joueur_id, "saison_podium"):
            nouveaux.append("saison_podium")
        if nouveaux:
            resultats[joueur_id] = nouveaux
    return resultats


def verifier_badges_expedition(conn, joueur_id: int, butin: list) -> list:
    """Badges déclenchés après réclamation d'une expédition."""
    nouveaux = []

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM expeditions WHERE joueur_id = %s AND reclamee = TRUE",
            (joueur_id,),
        )
        count = cur.fetchone()[0]

    for code, seuil in [("explorateur", 1), ("routard", 10)]:
        if count >= seuil and db.attribuer_badge(conn, joueur_id, code):
            nouveaux.append(code)

    if any(item["code"] == "essence_neant" for item in butin):
        if db.attribuer_badge(conn, joueur_id, "chasseur_tresors"):
            nouveaux.append("chasseur_tresors")

    return nouveaux
