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

    return nouveaux
