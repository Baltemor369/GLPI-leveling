"""
Worker principal — tourne en boucle toutes les SYNC_INTERVAL_SECONDS secondes.
Pour chaque ticket clos non encore traité :
  1. Analyse LLM : score conformité (Annexe B) + score difficulté (Annexe A)
  2. XP résolution → technicien assigné
  3. XP conformité → technicien créateur du ticket (user_editor)
  4. Enregistrement anti-doublon
"""

import re
import time

import db
import badge_engine
from config import SYNC_INTERVAL_SECONDS
from glpi_client import GlpiClient
from ollama_client import analyser_ticket
from xp_engine import calculer_xp_resolution, calculer_xp_conformite

STATUS_CLOS = 6


def _nettoyer_html(texte: str) -> str:
    return re.sub(r"<[^>]+>", " ", texte or "").strip()


def traiter_ticket(conn, glpi: GlpiClient, ticket: dict):
    tid = ticket["id"]

    if db.ticket_deja_traite(conn, tid):
        return

    # ── Technicien assigné (résolveur) ────────────────────────────────────
    equipe   = ticket.get("team", [])
    assigned = next((m for m in equipe if m["role"] == "assigned"), None)
    if not assigned:
        print(f"  Ticket #{tid} ignoré : aucun technicien assigné.")
        return

    joueur_id = assigned["id"]
    username  = assigned.get("display_name", assigned["name"])
    db.get_or_create_joueur(conn, joueur_id, username)

    # ── Technicien créateur (user_editor) ─────────────────────────────────
    user_editor = ticket.get("user_editor") or {}
    createur_id = user_editor.get("id")
    createur_nom = user_editor.get("name", "")

    # Ne créer le joueur créateur que s'il est différent du résolveur
    if createur_id and createur_id != joueur_id and createur_nom:
        db.get_or_create_joueur(conn, createur_id, createur_nom)

    # ── Données ticket ────────────────────────────────────────────────────
    nom_categorie = (ticket.get("category") or {}).get("name", "")
    urgence       = ticket.get("urgency", 3)
    impact        = ticket.get("impact",  3)
    date_creation = ticket.get("date_creation") or ticket.get("date", "")
    date_cloture  = ticket.get("date_close") or ticket.get("date_solve", "")

    titre       = ticket.get("name", "")
    description = _nettoyer_html(glpi.get_ticket_description(tid))

    # ── Analyse LLM (un seul appel) ───────────────────────────────────────
    print(f"  Ticket #{tid} — analyse LLM en cours...")
    analyse = analyser_ticket(titre, description, solution="")

    score_conf   = analyse["score_conformite"]
    expl_conf    = analyse["explication_conformite"]
    score_diff   = analyse["score_difficulte"]
    expl_diff    = analyse["explication_difficulte"]

    # ── Calcul XP résolution (technicien assigné) ─────────────────────────
    xp_resolution = calculer_xp_resolution(
        nom_categorie  = nom_categorie,
        urgence        = urgence,
        impact         = impact,
        score_difficulte = score_diff,
        date_creation  = date_creation,
        date_cloture   = date_cloture,
    )

    # ── Calcul XP conformité (technicien créateur) ────────────────────────
    xp_conf = calculer_xp_conformite(nom_categorie, score_conf)

    # ── Attribution XP ────────────────────────────────────────────────────
    niveaux, nouveau_niv = db.ajouter_xp(conn, joueur_id, xp_resolution)

    if createur_id and createur_id != joueur_id:
        db.ajouter_xp(conn, createur_id, xp_conf)
    else:
        # Même personne : cumule les deux XP
        db.ajouter_xp(conn, joueur_id, xp_conf)

    # ── Enregistrement ────────────────────────────────────────────────────
    db.enregistrer_ticket(
        conn               = conn,
        ticket_id          = tid,
        joueur_id          = joueur_id,
        xp_gagne           = xp_resolution,
        score_difficulte   = score_diff,
        analyse_llm        = expl_diff,
        createur_id        = createur_id if createur_id != joueur_id else None,
        xp_conformite      = xp_conf,
        score_conformite   = score_conf,
        analyse_conformite = expl_conf,
        nom_categorie      = nom_categorie,
    )

    # ── Badges ────────────────────────────────────────────────────────────────
    badge_engine.verifier_badges_ticket(conn, joueur_id, nom_categorie, date_creation, date_cloture)
    badge_engine.verifier_badges_conformite(conn, createur_id if createur_id != joueur_id else None, score_conf)
    if niveaux and nouveau_niv:
        badge_engine.verifier_badges_niveau(conn, joueur_id, nouveau_niv)

    print(
        f"  Ticket #{tid} [{nom_categorie or '?'}] -> {username}"
        f" +{xp_resolution} XP (diff {score_diff}/10)"
        f" | Conformite {score_conf}/10 -> {createur_nom or username} +{xp_conf} XP"
        f"{' | NIVEAU ' + str(nouveau_niv) + ' !' if niveaux else ''}"
    )


def enregistrer_techniciens(conn, tickets: list):
    """Pré-enregistre tout technicien assigné (tous statuts) comme joueur 0 XP."""
    for ticket in tickets:
        assigned = next((m for m in ticket.get("team", []) if m["role"] == "assigned"), None)
        if assigned:
            db.get_or_create_joueur(conn, assigned["id"],
                                    assigned.get("display_name", assigned["name"]))


def boucle_principale():
    print("Worker GlpiLeveling démarré.")
    db.init_db()
    glpi = GlpiClient()

    while True:
        print(f"\n[Sync] Vérification des tickets...")
        try:
            conn    = db.get_conn()
            tickets = glpi.get_tickets()

            # Pass 1 : enregistrer tous les techs assignés
            enregistrer_techniciens(conn, tickets)

            # Pass 2 : attribuer XP pour les tickets clos
            clos = [t for t in tickets if t["status"]["id"] == STATUS_CLOS]
            print(f"  {len(clos)} ticket(s) clos trouvé(s).")
            for ticket in clos:
                traiter_ticket(conn, glpi, ticket)

            # Pass 3 : purger les sessions expirées
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE expires < NOW()")
            conn.commit()

            conn.close()
        except Exception as e:
            print(f"  Erreur : {e}")

        time.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    boucle_principale()
