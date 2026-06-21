from flask import Blueprint, session, redirect, url_for, render_template, flash, request
from ..auth import login_required
from .. import queries
from db import xp_requis_pour_niveau

aventurier_bp = Blueprint("aventurier", __name__)


@aventurier_bp.route("/")
@login_required
def index():
    joueur_id = session["joueur_id"]
    joueur = queries.get_joueur(joueur_id)
    if not joueur:
        flash("Profil introuvable.", "error")
        return redirect(url_for("auth.logout"))

    equipements = queries.get_equipements(joueur_id)
    tickets = queries.get_tickets_joueur(joueur_id, limit=5)

    xp_actuel  = joueur["xp"]
    niveau     = joueur["level"]
    xp_suivant = xp_requis_pour_niveau(niveau + 1)
    xp_prec    = xp_requis_pour_niveau(niveau)
    xp_dans    = xp_actuel - xp_prec
    xp_nec     = max(1, xp_suivant - xp_prec)
    pct        = min(100, int(xp_dans / xp_nec * 100))

    equipes = [e for e in equipements if e["equipe"]]

    return render_template(
        "aventurier.html",
        joueur=joueur,
        equipements=equipements,
        equipes=equipes,
        tickets=tickets,
        xp_actuel=xp_actuel,
        xp_suivant=xp_suivant,
        pct=pct,
        active="aventurier",
    )


@aventurier_bp.route("/stat/depenser", methods=["POST"])
@login_required
def depenser_stat():
    stat = request.form.get("stat", "")
    joueur_id = session["joueur_id"]
    try:
        ok = queries.depenser_point_stat(joueur_id, stat)
        if not ok:
            flash("Aucun point disponible.", "error")
    except ValueError:
        flash("Statistique invalide.", "error")
    return redirect(url_for("aventurier.index"))
