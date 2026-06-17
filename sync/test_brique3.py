"""
Test de la Brique 3 : vérifie la connexion PostgreSQL, le schéma, et simule
le traitement complet d'un ticket clos (XP + niveau + enregistrement).
"""

import db
from glpi_client import GlpiClient
from ollama_client import analyser_conformite
from xp_engine import calculer_xp

STATUS_CLOS = 6

if __name__ == "__main__":
    print("=== Test Brique 3 : Base de données + Logique RPG ===\n")

    # 1. Connexion et initialisation du schéma
    conn = db.get_conn()
    db.init_db()
    print("Connexion PostgreSQL : OK\n")

    # 2. Traitement de tous les tickets clos
    glpi = GlpiClient()
    tickets = glpi.get_tickets()
    clos = [t for t in tickets if t["status"]["id"] == STATUS_CLOS]
    print(f"{len(clos)} ticket(s) clos a traiter.\n")

    for ticket in clos:
        tid = ticket["id"]
        titre = ticket["name"]
        priorite = ticket.get("priority", 3)
        categorie_id = (ticket.get("category") or {}).get("id", 0)

        # Technicien assigné
        equipe = ticket.get("team", [])
        assigned = next((m for m in equipe if m["role"] == "assigned"), None)
        if not assigned:
            print(f"Ticket #{tid} : aucun technicien assigné, ignore.")
            continue

        joueur_id = assigned["id"]
        username = assigned.get("display_name", assigned["name"])
        db.get_or_create_joueur(conn, joueur_id, username)

        # Conformité
        description = glpi.get_ticket_description(tid)
        resultat = analyser_conformite(titre, description)
        conforme = resultat["conforme"]

        # XP
        xp_gagne, or_gagne = calculer_xp(priorite, categorie_id, conforme)

        print(f"--- Ticket #{tid} : {titre} ---")
        print(f"  Priorite       : {priorite}")
        print(f"  Categorie id   : {categorie_id}")
        print(f"  Conforme       : {'OUI' if conforme else 'NON'}")
        print(f"  XP calcule     : {xp_gagne}")
        print(f"  Or calcule     : {or_gagne}")

        if db.ticket_deja_traite(conn, tid):
            print(f"  Deja traite, ignore.\n")
            continue

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE joueurs SET or_monnaie = or_monnaie + %s WHERE id = %s",
                (or_gagne, joueur_id),
            )
        niveaux_gagnes, nouveau_niveau = db.ajouter_xp(conn, joueur_id, xp_gagne)
        db.enregistrer_ticket(conn, tid, joueur_id, xp_gagne, conforme, resultat["explication"])

        print(f"  Niveaux gagnes : {niveaux_gagnes} (niveau actuel : {nouveau_niveau})")
        print()

    # 3. Afficher l'état des joueurs en base
    print("\n=== Etat des joueurs en base ===")
    with conn.cursor() as cur:
        cur.execute("SELECT id, username, level, xp, or_monnaie, force_p, constitution_pv, agilite_vit, esprit_res, points_a_attribuer FROM joueurs ORDER BY xp DESC")
        rows = cur.fetchall()
        for r in rows:
            print(f"  [{r[1]}] Niv.{r[2]} | XP:{r[3]} | Or:{r[4]} | FOR:{r[5]} CON:{r[6]} AGI:{r[7]} ESP:{r[8]} | Points dispo:{r[9]}")

    conn.close()
