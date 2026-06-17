from glpi_client import GlpiClient
from ollama_client import analyser_conformite

if __name__ == "__main__":
    client = GlpiClient()
    tickets = client.get_tickets()

    print(f"Analyse de conformite sur {len(tickets)} ticket(s)...\n")

    for ticket in tickets:
        tid = ticket["id"]
        titre = ticket["name"]
        statut = ticket["status"]["name"]
        description = client.get_ticket_description(tid)

        print(f"{'='*60}")
        print(f"Ticket #{tid} - {titre} [{statut}]")
        print(f"Description : {description if description else '(vide)'}")
        print()

        resultat = analyser_conformite(titre, description)
        print(f"Conforme      : {'[OUI]' if resultat['conforme'] else '[NON]'}")
        if resultat["criteres_manquants"]:
            print(f"Manquants     : {', '.join(resultat['criteres_manquants'])}")
        print(f"Explication   : {resultat['explication']}")
        print()
