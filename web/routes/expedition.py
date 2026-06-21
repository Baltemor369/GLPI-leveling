import random
from datetime import datetime, timezone
from flask import Blueprint, session, render_template, redirect, url_for, request, flash
from ..auth import login_required
from db import (
    get_conn, get_expedition_active, lancer_expedition,
    marquer_reclamee, ajouter_materiau, get_materiaux,
)
from badge_engine import verifier_badges_expedition

expedition_bp = Blueprint("expedition", __name__)

DUREE_HEURES = 2
NB_ROLLS     = 3
PITY_SEUIL   = 10

LOOT_TABLE = [
    {"code": "or",              "nom": "Or",               "icone": "💰", "poids": 38, "min": 5,  "max": 15},
    {"code": "bois_chene",      "nom": "Bois de Chêne",    "icone": "🌲", "poids": 28, "min": 2,  "max": 4},
    {"code": "minerai_fer",     "nom": "Minerai de Fer",   "icone": "⚙️", "poids": 20, "min": 1,  "max": 3},
    {"code": "cristal_runique", "nom": "Cristal Runique",  "icone": "💎", "poids": 10, "min": 1,  "max": 2},
    {"code": "essence_neant",   "nom": "Essence du Néant", "icone": "✨", "poids": 4,  "min": 1,  "max": 1},
]
_POIDS   = [i["poids"] for i in LOOT_TABLE]
_ESSENCE = next(i for i in LOOT_TABLE if i["code"] == "essence_neant")


def _rouler_loot(pity: int) -> tuple[list[dict], bool]:
    butin_dict = {}
    essence = False
    restants = NB_ROLLS

    if pity >= PITY_SEUIL:
        qty = random.randint(_ESSENCE["min"], _ESSENCE["max"])
        butin_dict["essence_neant"] = qty
        essence = True
        restants -= 1

    for _ in range(restants):
        item = random.choices(LOOT_TABLE, weights=_POIDS, k=1)[0]
        qty  = random.randint(item["min"], item["max"])
        butin_dict[item["code"]] = butin_dict.get(item["code"], 0) + qty
        if item["code"] == "essence_neant":
            essence = True

    butin = []
    for code, qty in butin_dict.items():
        info = next(i for i in LOOT_TABLE if i["code"] == code)
        butin.append({"code": code, "nom": info["nom"], "icone": info["icone"], "quantite": qty})
    return butin, essence


def _get_pity(conn, jid: int) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT pity_expedition FROM joueurs WHERE id = %s", (jid,))
        row = cur.fetchone()
        return row[0] if row else 0


def _set_pity(conn, jid: int, pity: int):
    with conn.cursor() as cur:
        cur.execute("UPDATE joueurs SET pity_expedition = %s WHERE id = %s", (pity, jid))


def _expedition_status_data(joueur_id: int) -> dict:
    conn = get_conn()
    try:
        expedition = get_expedition_active(conn, joueur_id)
        if expedition is None:
            return {"statut": "aucune"}

        now = datetime.now(timezone.utc)
        fin = expedition["fin"]
        if fin.tzinfo is None:
            fin = fin.replace(tzinfo=timezone.utc)

        if now >= fin:
            return {"statut": "terminee", "expedition": expedition}

        secondes_restantes = (fin - now).total_seconds()
        heures   = int(secondes_restantes // 3600)
        minutes  = int((secondes_restantes % 3600) // 60)
        secondes = int(secondes_restantes % 60)
        pct = max(0.0, 1 - secondes_restantes / (DUREE_HEURES * 3600))
        retour = fin.astimezone().strftime("%H:%M")
        return {
            "statut": "en_cours",
            "timer": f"{heures:02d}:{minutes:02d}:{secondes:02d}",
            "pct": pct * 100,
            "retour": retour,
            "expedition": expedition,
        }
    finally:
        conn.close()


@expedition_bp.route("/expedition")
@login_required
def index():
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        stock = get_materiaux(conn, joueur_id)
        pity  = _get_pity(conn, joueur_id)
        with conn.cursor() as cur:
            cur.execute("SELECT or_monnaie FROM joueurs WHERE id = %s", (joueur_id,))
            row = cur.fetchone()
            stock["or"] = row[0] if row else 0
    finally:
        conn.close()

    status = _expedition_status_data(joueur_id)

    total_poids = sum(_POIDS)
    loot_proba = [
        {**item, "pct": item["poids"] / total_poids * 100}
        for item in LOOT_TABLE
    ]

    return render_template(
        "expedition.html",
        stock=stock,
        pity=pity,
        pity_seuil=PITY_SEUIL,
        loot_table=loot_proba,
        status=status,
        active="expedition",
    )


@expedition_bp.route("/expedition/status")
@login_required
def status():
    joueur_id = session["joueur_id"]
    status = _expedition_status_data(joueur_id)
    return render_template("partials/expedition_status.html", status=status)


@expedition_bp.route("/expedition/lancer", methods=["POST"])
@login_required
def lancer():
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        lancer_expedition(conn, joueur_id, DUREE_HEURES)
        flash("Expédition lancée ! Revenez dans 2 heures.", "success")
    finally:
        conn.close()
    return redirect(url_for("expedition.index"))


@expedition_bp.route("/expedition/reclamer", methods=["POST"])
@login_required
def reclamer():
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        expedition = get_expedition_active(conn, joueur_id)
        if not expedition:
            flash("Aucune expédition en cours.", "error")
            return redirect(url_for("expedition.index"))

        pity = _get_pity(conn, joueur_id)
        butin, essence_obtenue = _rouler_loot(pity)
        pity_info = "garanti" if pity >= PITY_SEUIL else None

        if not marquer_reclamee(conn, expedition["id"]):
            conn.rollback()
            flash("Cette expédition a déjà été réclamée.", "warning")
            return redirect(url_for("expedition.index"))

        for item in butin:
            if item["code"] == "or":
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE joueurs SET or_monnaie = or_monnaie + %s WHERE id = %s",
                        (item["quantite"], joueur_id),
                    )
            else:
                ajouter_materiau(conn, joueur_id, item["code"], item["quantite"])

        nouveau_pity = 0 if essence_obtenue else pity + 1
        _set_pity(conn, joueur_id, nouveau_pity)
        conn.commit()

        try:
            nouveaux_badges = verifier_badges_expedition(conn, joueur_id, butin)
        except Exception:
            nouveaux_badges = []
    finally:
        conn.close()

    flash("🎉 Expédition terminée ! Voici votre butin :", "success")
    if pity_info == "garanti":
        flash("✨ Pity activé — Essence du Néant garantie !", "info")
    for item in butin:
        flash(f"{item['icone']} {item['nom']} +{item['quantite']}", "loot")
    for code in nouveaux_badges:
        flash(f"🏅 Badge débloqué : {code} !", "success")

    return redirect(url_for("expedition.index"))
