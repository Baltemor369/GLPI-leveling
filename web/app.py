import os
from flask import Flask, session
from .routes.auth import auth_bp
from .routes.aventurier import aventurier_bp
from .routes.classement import classement_bp
from .routes.journal import journal_bp
from .routes.forge import forge_bp
from .routes.arene import arene_bp
from .routes.badges import badges_bp
from .routes.expedition import expedition_bp
from . import queries


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ["SECRET_KEY"]
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.register_blueprint(auth_bp)
    app.register_blueprint(aventurier_bp)
    app.register_blueprint(classement_bp)
    app.register_blueprint(journal_bp)
    app.register_blueprint(forge_bp)
    app.register_blueprint(arene_bp)
    app.register_blueprint(badges_bp)
    app.register_blueprint(expedition_bp)

    @app.context_processor
    def inject_sidebar():
        if "joueur_id" in session:
            try:
                joueur = queries.get_joueur(session["joueur_id"])
                return {"sidebar_joueur": joueur}
            except Exception:
                pass
        return {"sidebar_joueur": None}

    return app


app = create_app()
