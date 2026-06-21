from flask import Blueprint, session, render_template
from ..auth import login_required
from db import get_conn, get_badges_joueur

badges_bp = Blueprint("badges", __name__)


@badges_bp.route("/badges")
@login_required
def index():
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        badges = get_badges_joueur(conn, joueur_id)
    finally:
        conn.close()

    debloque   = [b for b in badges if b["date_obtenu"] is not None]
    verrouille = [b for b in badges if b["date_obtenu"] is None]

    return render_template(
        "badges.html",
        debloque=debloque,
        verrouille=verrouille,
        total=len(badges),
        active="badges",
    )
