import time

import requests

from config import (
    GLPI_API_BASE_URL,
    GLPI_BOT_PASSWORD,
    GLPI_BOT_USERNAME,
    GLPI_OAUTH_CLIENT_ID,
    GLPI_OAUTH_CLIENT_SECRET,
)


class GlpiClient:
    def __init__(self):
        self.access_token = None
        self.expires_at = 0

    def _fetch_token(self):
        response = requests.post(
            f"{GLPI_API_BASE_URL}/token",
            data={
                "grant_type": "password",
                "client_id": GLPI_OAUTH_CLIENT_ID,
                "client_secret": GLPI_OAUTH_CLIENT_SECRET,
                "username": GLPI_BOT_USERNAME,
                "password": GLPI_BOT_PASSWORD,
                "scope": "api",
            },
        )
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]
        self.expires_at = time.time() + data["expires_in"] - 30

    def _ensure_token(self):
        if self.access_token is None or time.time() >= self.expires_at:
            self._fetch_token()

    def _headers(self):
        self._ensure_token()
        return {"Authorization": f"Bearer {self.access_token}"}

    def get_tickets(self, **params):
        response = requests.get(
            f"{GLPI_API_BASE_URL}/v2.3/Assistance/Ticket",
            headers=self._headers(),
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_ticket(self, ticket_id):
        response = requests.get(
            f"{GLPI_API_BASE_URL}/v2.3/Assistance/Ticket/{ticket_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_ticket_description(self, ticket_id):
        import re
        ticket = self.get_ticket(ticket_id)
        raw = ticket.get("content", "")
        return re.sub(r"<[^>]+>", " ", raw).strip()
