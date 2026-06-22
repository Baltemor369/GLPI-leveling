import logging
import os
from datetime import datetime, timezone
from flask import Flask, session
from db import xp_requis_pour_niveau
from .extensions import csrf, limiter
from .routes.auth import auth_bp
from .routes.aventurier import aventurier_bp
from .routes.classement import classement_bp
from .routes.journal import journal_bp
from .routes.forge import forge_bp
from .routes.arene import arene_bp
from .routes.badges import badges_bp
from .routes.expedition import expedition_bp
from . import queries

_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://unpkg.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)

_log = logging.getLogger(__name__)

_VERSION_FILE = os.path.join(os.path.dirname(__file__), os.pardir, "VERSION")


def _lire_version() -> str:
    """Read the application version from the VERSION file (single source of truth)."""
    try:
        with open(_VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "?"


APP_VERSION = _lire_version()

# Empty sidebar context returned whenever no session is active or the player
# row cannot be fetched. Defined at module level so it is not recreated on
# every request.
_SIDEBAR_VIDE = {
    "sidebar_joueur": None,
    "sidebar_xp_restant": 0,
    "sidebar_saison": None,
    "sidebar_reset_jours": 0,
    "sidebar_reset_heures": 0,
}


def _countdown_reset_saison() -> tuple[int, int]:
    """Return (days, hours) remaining until the next monthly season reset.

    The reset fires on the 1st of each month at 00:00 UTC (see worker
    ``_verifier_reset_saison``). This countdown is computed from the frontend
    UTC clock; any skew against the database clock is negligible for a display
    indicator.
    """
    maintenant = datetime.now(timezone.utc)
    if maintenant.month == 12:
        prochain = datetime(maintenant.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        prochain = datetime(maintenant.year, maintenant.month + 1, 1, tzinfo=timezone.utc)
    delta = prochain - maintenant
    return delta.days, delta.seconds // 3600


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ["SECRET_KEY"]
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    csrf.init_app(app)
    limiter.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(aventurier_bp)
    app.register_blueprint(classement_bp)
    app.register_blueprint(journal_bp)
    app.register_blueprint(forge_bp)
    app.register_blueprint(arene_bp)
    app.register_blueprint(badges_bp)
    app.register_blueprint(expedition_bp)

    @app.context_processor
    def inject_version():
        # Available on every page, including the login page (no session required).
        return {"app_version": APP_VERSION}

    @app.context_processor
    def inject_sidebar():
        """Expose the connected player's sidebar data to every template.

        Returns ``_SIDEBAR_VIDE`` (all keys empty) when no session is active
        or the player row cannot be fetched, so templates can always rely on
        the keys being present. When a player is connected it provides the
        player row, XP remaining before the next level, the current season and
        the days/hours remaining until the monthly reset.
        """
        if "joueur_id" not in session:
            return dict(_SIDEBAR_VIDE)
        try:
            joueur = queries.get_joueur(session["joueur_id"])
        except Exception as exc:
            _log.warning("get_joueur() échoué dans la sidebar : %s", exc)
            return dict(_SIDEBAR_VIDE)
        if not joueur:
            return dict(_SIDEBAR_VIDE)

        # XP remaining until the next level (displayed below the current level).
        xp_suivant = xp_requis_pour_niveau(joueur["level"] + 1)
        xp_restant = max(0, xp_suivant - joueur["xp"])

        # Current season + countdown to the monthly reset.
        try:
            saison = queries.get_saison_courante()
        except Exception as exc:
            _log.warning("get_saison_courante() échoué dans la sidebar : %s", exc)
            saison = None
        reset_jours, reset_heures = _countdown_reset_saison()

        return {
            "sidebar_joueur": joueur,
            "sidebar_xp_restant": xp_restant,
            "sidebar_saison": saison,
            "sidebar_reset_jours": reset_jours,
            "sidebar_reset_heures": reset_heures,
        }

    @app.after_request
    def security_headers(response):
        response.headers["X-Frame-Options"]         = "DENY"
        response.headers["X-Content-Type-Options"]  = "nosniff"
        response.headers["Referrer-Policy"]         = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _CSP
        return response

    return app


app = create_app()
