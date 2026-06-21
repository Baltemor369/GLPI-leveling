from flask import Blueprint, render_template
from ..auth import login_required
from .. import queries

journal_bp = Blueprint("journal", __name__)


@journal_bp.route("/journal")
@login_required
def index():
    tickets = queries.get_tickets_tous(limit=50)

    total    = len(tickets)
    conformes = sum(1 for t in tickets if t["conforme"])
    xp_total  = sum(t["xp_gagne"] for t in tickets)
    taux_conf = int(conformes / total * 100) if total else 0

    return render_template(
        "journal.html",
        tickets=tickets,
        total=total,
        taux_conf=taux_conf,
        xp_total=xp_total,
        active="journal",
    )
