from glpi_client import GlpiClient

if __name__ == "__main__":
    client = GlpiClient()
    tickets = client.get_tickets()
    print(f"{len(tickets)} ticket(s) récupéré(s) :")
    for ticket in tickets:
        print(f"  #{ticket['id']} - {ticket['name']} (status={ticket['status']})")
