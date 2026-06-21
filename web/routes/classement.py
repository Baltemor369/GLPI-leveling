from flask import Blueprint, session, render_template, flash, request
from ..auth import login_required
from .. import queries
from db import xp_requis_pour_niveau

classement_bp = Blueprint("classement", __name__)


@classement_bp.route("/classement")
@login_required
def index():
    joueur_id = session["joueur_id"]
    tab = request.args.get("tab", "xp")
    if tab not in ("xp", "pc"):
        tab = "xp"

    try:
        joueurs = queries.tous_les_joueurs_par_pc() if tab == "pc" else queries.tous_les_joueurs()
    except Exception:
        flash(
            "Impossible de charger le classement. Si la BDD est accessible : "
            "docker compose up -d --build worker",
            "error",
        )
        joueurs = []

    mon_rang = next((i + 1 for i, j in enumerate(joueurs) if j["id"] == joueur_id), None)

    return render_template(
        "classement.html",
        joueurs=joueurs,
        joueur_id=joueur_id,
        mon_rang=mon_rang,
        tab=tab,
        xp_requis_pour_niveau=xp_requis_pour_niveau,
        active="classement",
    )
