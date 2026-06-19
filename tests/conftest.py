"""Shared pytest setup for the GlpiLeveling test suite.

The production modules under ``sync/`` are written to be imported with that
directory on ``sys.path`` (the Docker image sets ``PYTHONPATH=/app/sync``).
Several of them (``config``, ``db``, ``badge_engine``) read database / GLPI
environment variables *at import time*, so we inject harmless dummy values
before any production module is imported. No real database or network is ever
contacted: every test mocks the psycopg2 connection/cursor.
"""

import os
import sys

# ── Dummy environment so ``config`` imports cleanly (no real services used) ──
os.environ.setdefault("GLPI_API_BASE_URL", "http://localhost")
os.environ.setdefault("GLPI_OAUTH_CLIENT_ID", "test")
os.environ.setdefault("GLPI_OAUTH_CLIENT_SECRET", "test")
os.environ.setdefault("GLPI_BOT_USERNAME", "test")
os.environ.setdefault("GLPI_BOT_PASSWORD", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")

# ── Make the production modules importable like in the container ────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SYNC_DIR = os.path.join(_PROJECT_ROOT, "sync")
if _SYNC_DIR not in sys.path:
    sys.path.insert(0, _SYNC_DIR)
