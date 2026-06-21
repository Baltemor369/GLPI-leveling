import html as html_mod
from flask import (
    Blueprint, session, render_template, redirect, url_for,
    request, flash, make_response,
)
from ..auth import login_required
from .. import queries
from db import get_conn
import psycopg2.extras
from combat_engine import (
    ACTIONS, creer_combat, accepter_combat, jouer_action,
    get_combat, get_combats_joueur,
    pv_max, force_effective, resistance_effective, agilite_effective, chance_esquive,
    _get_joueur, _get_equipements,
)

arene_bp = Blueprint("arene", __name__)


def _stats_joueur(conn, jid):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        j  = _get_joueur(cur, jid)
        eq = _get_equipements(cur, jid)
    return j, eq, pv_max(j, eq), force_effective(j, eq), resistance_effective(j, eq), agilite_effective(j, eq)


def _build_combat_ctx(conn, c, joueur_id):
    att_j, att_eq, att_pv_max, att_for, att_res, att_agi = _stats_joueur(conn, c["attaquant_id"])
    def_j, def_eq, def_pv_max, def_for, def_res, def_agi = _stats_joueur(conn, c["defenseur_id"])

    pv_att = c["pv_attaquant"]
    pv_def = c["pv_defenseur"]
    pct_att = max(0, int(pv_att / max(1, att_pv_max) * 100))
    pct_def = max(0, int(pv_def / max(1, def_pv_max) * 100))

    def color(pct):
        return "#4caf50" if pct > 50 else "#ff9800" if pct > 25 else "#f44336"

    lignes = []
    if c["log_combat"]:
        lignes = list(reversed(c["log_combat"].strip().split("\n")[-15:]))

    return dict(
        c=c, joueur_id=joueur_id,
        att_j=att_j, att_eq=att_eq, att_pv_max=att_pv_max,
        att_for=att_for, att_res=att_res, att_agi=att_agi,
        def_j=def_j, def_eq=def_eq, def_pv_max=def_pv_max,
        def_for=def_for, def_res=def_res, def_agi=def_agi,
        pv_att=pv_att, pv_def=pv_def,
        pct_att=pct_att, pct_def=pct_def,
        color_att=color(pct_att), color_def=color(pct_def),
        mon_tour=(c["tour_de_qui"] == joueur_id),
        lignes=lignes,
        ACTIONS=ACTIONS,
        chance_esquive=chance_esquive,
    )


def _victoire_msg(c, joueur_id):
    if c.get("vainqueur_id") == joueur_id:
        return "victoire"
    if c.get("vainqueur_id") is not None:
        return "defaite"
    return None


def _render_fin(c, joueur_id, nouveaux_badges=None):
    derniere = c["log_combat"].strip().split("\n")[-1] if c.get("log_combat") else "Combat terminé."
    return render_template(
        "partials/combat_fin.html",
        message=derniere,
        victoire=_victoire_msg(c, joueur_id),
        nouveaux_badges=nouveaux_badges or [],
    ), 286


@arene_bp.route("/arene")
@login_required
def index():
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        combats   = get_combats_joueur(conn, joueur_id)
        c_cours   = next((c for c in combats if c["statut"] == "en_cours"),   None)
        c_attente = next((c for c in combats if c["statut"] == "en_attente"), None)

        if c_cours:
            ctx = _build_combat_ctx(conn, c_cours, joueur_id)
            return render_template("arene/combat.html", mode="combat", active="arene", **ctx)

        if c_attente:
            est_def = c_attente["defenseur_id"] == joueur_id
            return render_template("arene/attente.html", mode="attente", c=c_attente,
                                   est_defenseur=est_def, active="arene")

        # Lobby
        try:
            tous_joueurs = queries.tous_les_joueurs()
        except Exception:
            flash("Impossible de charger la liste des joueurs. Vérifiez la migration BDD.", "error")
            tous_joueurs = []

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT c.*, ja.username AS nom_attaquant, jd.username AS nom_defenseur
                FROM combats c
                JOIN joueurs ja ON ja.id = c.attaquant_id
                JOIN joueurs jd ON jd.id = c.defenseur_id
                WHERE (c.attaquant_id = %s OR c.defenseur_id = %s) AND c.statut = 'termine'
                ORDER BY c.id DESC LIMIT 1
            """, (joueur_id, joueur_id))
            dernier = cur.fetchone()

        adversaires = [j for j in tous_joueurs if j["id"] != joueur_id]
        moi         = next((j for j in tous_joueurs if j["id"] == joueur_id), None)

        return render_template(
            "arene/lobby.html",
            mode="lobby", active="arene",
            adversaires=adversaires, moi=moi, dernier=dernier,
        )
    finally:
        conn.close()


@arene_bp.route("/arene/combat-partial")
@login_required
def combat_partial():
    combat_id = request.args.get("combat_id", type=int)
    joueur_id = session["joueur_id"]

    if combat_id is None:
        return render_template("partials/combat_fin.html",
                               message="Combat introuvable.", victoire=None,
                               nouveaux_badges=[]), 286

    conn = get_conn()
    try:
        c = get_combat(conn, combat_id)
        if not c or c["statut"] != "en_cours":
            if c and c["statut"] == "termine":
                return _render_fin(c, joueur_id)
            return render_template("partials/combat_fin.html",
                                   message="Ce combat n'est plus disponible.", victoire=None,
                                   nouveaux_badges=[]), 286
        ctx = _build_combat_ctx(conn, c, joueur_id)
    finally:
        conn.close()

    return render_template("partials/combat_partial.html", **ctx)


@arene_bp.route("/arene/attente-partial")
@login_required
def attente_partial():
    combat_id = request.args.get("combat_id", type=int)
    joueur_id = session["joueur_id"]

    if combat_id is None:
        return render_template("partials/attente_fin.html",
                               message="Défi introuvable."), 286

    conn = get_conn()
    try:
        combats = get_combats_joueur(conn, joueur_id)
        c = next((x for x in combats if x["id"] == combat_id), None)
    finally:
        conn.close()

    if not c or c["statut"] == "termine":
        return render_template("partials/attente_fin.html",
                               message="Ce défi a expiré ou n'est plus disponible."), 286

    if c["statut"] == "en_cours":
        resp = make_response("", 200)
        resp.headers["HX-Redirect"] = url_for("arene.index")
        return resp

    est_def = c["defenseur_id"] == joueur_id
    return render_template("partials/attente_partial.html", c=c, est_defenseur=est_def)


@arene_bp.route("/arene/defier", methods=["POST"])
@login_required
def defier():
    joueur_id    = session["joueur_id"]
    defenseur_id = request.form.get("defenseur_id", type=int)
    mise         = request.form.get("mise", 0, type=int)

    if not defenseur_id or defenseur_id == joueur_id:
        flash("Adversaire invalide.", "error")
        return redirect(url_for("arene.index"))

    conn = get_conn()
    try:
        creer_combat(conn, joueur_id, defenseur_id, mise)
    finally:
        conn.close()

    return redirect(url_for("arene.index"))


@arene_bp.route("/arene/accepter/<int:combat_id>", methods=["POST"])
@login_required
def accepter(combat_id):
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        err = accepter_combat(conn, combat_id, joueur_id)
        if err:
            flash(err, "error")
    finally:
        conn.close()
    return redirect(url_for("arene.index"))


@arene_bp.route("/arene/refuser/<int:combat_id>", methods=["POST"])
@login_required
def refuser(combat_id):
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM combats WHERE id = %s AND defenseur_id = %s",
                (combat_id, joueur_id),
            )
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("arene.index"))


@arene_bp.route("/arene/action", methods=["POST"])
@login_required
def action():
    joueur_id = session["joueur_id"]
    combat_id = request.form.get("combat_id", type=int)
    action_id = request.form.get("action_id", "")

    if combat_id is None:
        flash("Requête invalide.", "error")
        return redirect(url_for("arene.index"))

    conn = get_conn()
    try:
        result = jouer_action(conn, combat_id, joueur_id, action_id)

        if result.get("erreur"):
            flash(result["erreur"], "error")

        nouveaux_badges = result.get("nouveaux_badges", [])

        c = get_combat(conn, combat_id)
        if not c or c["statut"] != "en_cours":
            if c and c["statut"] == "termine":
                return _render_fin(c, joueur_id, nouveaux_badges)
            return render_template("partials/combat_fin.html",
                                   message="Combat terminé.", victoire=None,
                                   nouveaux_badges=[]), 286

        ctx = _build_combat_ctx(conn, c, joueur_id)
    finally:
        conn.close()

    if nouveaux_badges:
        ctx["nouveaux_badges"] = nouveaux_badges

    return render_template("partials/combat_partial.html", **ctx)
