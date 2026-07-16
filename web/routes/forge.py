from flask import Blueprint, session, render_template, redirect, url_for, request, flash
from ..auth import login_required
from .. import queries
from db import get_conn, get_materiaux, consommer_materiaux
import badge_engine

forge_bp = Blueprint("forge", __name__)

CATALOGUE = [
    {"nom": "Pentium I",           "type": "arme",   "bonus_stat": "force_p",         "valeur_bonus": 5,  "cout": 50,   "tier": 1, "passif_code": None,              "passif_desc": None},
    {"nom": "Core i3",             "type": "arme",   "bonus_stat": "force_p",         "valeur_bonus": 12, "cout": 150,  "tier": 2, "passif_code": None,              "passif_desc": None},
    {"nom": "Core i5",             "type": "arme",   "bonus_stat": "force_p",         "valeur_bonus": 22, "cout": 250,  "tier": 3, "passif_code": "saignement",      "passif_desc": "⚡ Overclock — 20% chance +3 dégâts bonus"},
    {"nom": "Core i7",             "type": "arme",   "bonus_stat": "force_p",         "valeur_bonus": 35, "cout": 500,  "tier": 4, "passif_code": "vampirisme",      "passif_desc": "💾 Cache Hit — récupère 25% des dégâts infligés"},
    {"nom": "CPU Quantique",       "type": "arme",   "bonus_stat": "force_p",         "valeur_bonus": 50, "cout": 2000, "tier": 5, "passif_code": "execution",       "passif_desc": "💀 Kill Process — adverse < 20% PV → dégâts ×1.5"},
    {"nom": "Pare-feu basique",    "type": "armure", "bonus_stat": "esprit_res",      "valeur_bonus": 5,  "cout": 50,   "tier": 1, "passif_code": None,              "passif_desc": None},
    {"nom": "Antivirus",           "type": "armure", "bonus_stat": "esprit_res",      "valeur_bonus": 12, "cout": 150,  "tier": 2, "passif_code": None,              "passif_desc": None},
    {"nom": "Chiffrement AES",     "type": "armure", "bonus_stat": "esprit_res",      "valeur_bonus": 22, "cout": 250,  "tier": 3, "passif_code": "bouclier_pv",     "passif_desc": "🧱 Sandbox — +5% RES basé sur votre RAM max"},
    {"nom": "IDS/IPS",             "type": "armure", "bonus_stat": "esprit_res",      "valeur_bonus": 35, "cout": 500,  "tier": 4, "passif_code": "epines",          "passif_desc": "🔥 Honeypot — renvoie 15% des dégâts reçus"},
    {"nom": "Zero Trust",          "type": "armure", "bonus_stat": "esprit_res",      "valeur_bonus": 50, "cout": 2000, "tier": 5, "passif_code": "immunite",        "passif_desc": "🛡️ Air Gap — 25% chance d'ignorer les dégâts"},
    {"nom": "Barrette RAM",        "type": "amul",   "bonus_stat": "constitution_pv", "valeur_bonus": 8,  "cout": 50,   "tier": 1, "passif_code": None,              "passif_desc": None},
    {"nom": "Carte réseau",        "type": "amul",   "bonus_stat": "agilite_vit",     "valeur_bonus": 6,  "cout": 150,  "tier": 2, "passif_code": None,              "passif_desc": None},
    {"nom": "SSD NVMe",            "type": "amul",   "bonus_stat": "constitution_pv", "valeur_bonus": 15, "cout": 250,  "tier": 3, "passif_code": "regeneration",    "passif_desc": "💾 Auto-heal — récupère 5% RAM max/tour"},
    {"nom": "Fibre optique",       "type": "amul",   "bonus_stat": "agilite_vit",     "valeur_bonus": 10, "cout": 500,  "tier": 4, "passif_code": "celerite_niveau", "passif_desc": "📶 Low Latency — +0.5% esquive par niveau"},
    {"nom": "Cœur IA",             "type": "amul",   "bonus_stat": "constitution_pv", "valeur_bonus": 20, "cout": 2000, "tier": 5, "passif_code": "transcendance",   "passif_desc": "✨ Machine Learning — toutes les stats +1 par 2 niveaux"},
]

MATERIAUX_REQUIS = {
    3: {"minerai_fer":     3},
    4: {"cristal_runique": 2},
    5: {"essence_neant":   1},
}

TIER_COLORS = {1: "#7a6a55", 2: "#8fbf8f", 3: "#6ab0e8", 4: "#35c5f0", 5: "#e05c5c"}
STAT_LABELS = {"force_p": "CPU", "esprit_res": "Firewall", "constitution_pv": "RAM", "agilite_vit": "Débit"}
MAT_NOMS    = {"bois_chene": "🔌 Câble réseau", "minerai_fer": "🔩 Silicium",
               "cristal_runique": "🔷 Circuit imprimé", "essence_neant": "⚛️ Qubit"}

# Améliorer un équipement coûte 60% du coût de base, croît avec le palier,
# et bénéficie d'une remise de 30% si le joueur possède du câble réseau.
COUT_UPGRADE_RATIO = 0.6
REMISE_BOIS        = 0.7
AMELIORATION_MAX   = 20


def cout_amelioration(cout_base: int, amelioration: int, a_bois: bool) -> int:
    remise = REMISE_BOIS if a_bois else 1
    return round(cout_base * (amelioration + 1) * COUT_UPGRADE_RATIO * remise)


@forge_bp.route("/forge")
@login_required
def index():
    joueur_id = session["joueur_id"]
    joueur = queries.get_joueur(joueur_id)
    if not joueur:
        flash("Profil introuvable.", "error")
        return redirect(url_for("aventurier.index"))

    conn = get_conn()
    stock = get_materiaux(conn, joueur_id)
    conn.close()

    equipements = queries.get_equipements(joueur_id)

    catalogue_enrichi = []
    for item in CATALOGUE:
        mat_requis   = MATERIAUX_REQUIS.get(item["tier"], {})
        assez_or     = joueur["or_monnaie"] >= item["cout"]
        assez_mat    = all(stock.get(c, 0) >= q for c, q in mat_requis.items())
        catalogue_enrichi.append({
            **item,
            "mat_requis":   mat_requis,
            "peut_acheter": assez_or and assez_mat,
            "tier_color":   TIER_COLORS[item["tier"]],
        })

    inventaire = []
    for item in equipements:
        amelioration = item.get("amelioration", 0)
        cout_base    = item.get("cout_base", 50)
        a_bois       = stock.get("bois_chene", 0) > 0
        cout_upgrade = cout_amelioration(cout_base, amelioration, a_bois)
        inventaire.append({
            **item,
            "stat_totale":    item["valeur_bonus"] + amelioration * 2,
            "tier_color":     TIER_COLORS.get(item.get("tier", 1), "#7a6a55"),
            "cout_upgrade":   cout_upgrade,
            "peut_ameliorer": joueur["or_monnaie"] >= cout_upgrade and amelioration < AMELIORATION_MAX,
            "bois_remise":    a_bois,
        })

    return render_template(
        "forge.html",
        joueur=joueur, stock=stock,
        catalogue=catalogue_enrichi, inventaire=inventaire,
        stat_labels=STAT_LABELS, mat_noms=MAT_NOMS,
        active="forge",
    )


@forge_bp.route("/forge/acheter", methods=["POST"])
@login_required
def acheter():
    joueur_id = session["joueur_id"]
    nom = request.form.get("nom", "")

    item = next((i for i in CATALOGUE if i["nom"] == nom), None)
    if not item:
        flash("Équipement inconnu.", "error")
        return redirect(url_for("forge.index"))

    mat_requis = MATERIAUX_REQUIS.get(item["tier"], {})

    conn = get_conn()
    try:
        # Vérification serveur des matériaux avant toute écriture
        if mat_requis:
            stock = get_materiaux(conn, joueur_id)
            for code, qty in mat_requis.items():
                if stock.get(code, 0) < qty:
                    flash(f"Matériaux insuffisants : {MAT_NOMS.get(code, code)} manquant.", "error")
                    return redirect(url_for("forge.index"))

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE joueurs SET or_monnaie = or_monnaie - %s "
                "WHERE id = %s AND or_monnaie >= %s RETURNING id",
                (item["cout"], joueur_id, item["cout"]),
            )
            if cur.fetchone() is None:
                conn.rollback()
                flash("Crédits insuffisants.", "error")
                return redirect(url_for("forge.index"))
            cur.execute(
                """INSERT INTO equipements
                       (joueur_id, nom, type, bonus_stat, valeur_bonus,
                        passif_code, cout_base, tier)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (joueur_id, item["nom"], item["type"], item["bonus_stat"],
                 item["valeur_bonus"], item["passif_code"], item["cout"], item["tier"]),
            )
            # Consommation matériaux dans la même transaction avant commit
            if mat_requis:
                ok = consommer_materiaux(conn, joueur_id, mat_requis)
                if not ok:
                    conn.rollback()
                    flash("Matériaux insuffisants (stock modifié).", "error")
                    return redirect(url_for("forge.index"))

        conn.commit()  # commit unique : or + équipement + matériaux
        nouveaux = badge_engine.verifier_badges_forge(conn, joueur_id)
        flash(f"✅ {item['nom']} forgé !", "success")
        for code in nouveaux:
            flash(f"🎖️ Certification débloquée : {code} !", "success")
    finally:
        conn.close()

    return redirect(url_for("forge.index"))


@forge_bp.route("/forge/equiper/<int:equip_id>", methods=["POST"])
@login_required
def equiper(equip_id):
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT type FROM equipements WHERE id = %s AND joueur_id = %s",
                (equip_id, joueur_id),
            )
            row = cur.fetchone()
            if not row:
                flash("Équipement introuvable.", "error")
                return redirect(url_for("forge.index"))
            type_eq = row[0]
            cur.execute(
                "UPDATE equipements SET equipe = FALSE WHERE joueur_id = %s AND type = %s",
                (joueur_id, type_eq),
            )
            cur.execute("UPDATE equipements SET equipe = TRUE WHERE id = %s", (equip_id,))
        conn.commit()
        nouveaux = badge_engine.verifier_badges_forge(conn, joueur_id)
        for code in nouveaux:
            flash(f"🎖️ Certification débloquée : {code} !", "success")
    finally:
        conn.close()
    return redirect(url_for("forge.index"))


@forge_bp.route("/forge/desequiper/<int:equip_id>", methods=["POST"])
@login_required
def desequiper(equip_id):
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Le WHERE sur joueur_id garantit qu'un joueur ne déséquipe que ses
            # propres objets (protection IDOR) ; RETURNING permet de détecter
            # un id inconnu ou un objet déjà déséquipé.
            cur.execute(
                "UPDATE equipements SET equipe = FALSE "
                "WHERE id = %s AND joueur_id = %s AND equipe = TRUE RETURNING id",
                (equip_id, joueur_id),
            )
            if cur.fetchone() is None:
                conn.rollback()
                flash("Équipement introuvable ou déjà déséquipé.", "error")
                return redirect(url_for("forge.index"))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("forge.index"))


@forge_bp.route("/forge/ameliorer/<int:equip_id>", methods=["POST"])
@login_required
def ameliorer(equip_id):
    joueur_id = session["joueur_id"]
    conn = get_conn()
    try:
        stock  = get_materiaux(conn, joueur_id)
        a_bois = stock.get("bois_chene", 0) > 0

        with conn.cursor() as cur:
            cur.execute(
                "SELECT amelioration, cout_base FROM equipements WHERE id = %s AND joueur_id = %s",
                (equip_id, joueur_id),
            )
            row = cur.fetchone()
            if not row or row[0] >= AMELIORATION_MAX:
                flash("Amélioration impossible.", "error")
                return redirect(url_for("forge.index"))

            amelioration, cout_base = row
            cout_upgrade = cout_amelioration(cout_base, amelioration, a_bois)

            cur.execute(
                "UPDATE equipements SET amelioration = amelioration + 1 WHERE id = %s",
                (equip_id,),
            )
            cur.execute(
                "UPDATE joueurs SET or_monnaie = or_monnaie - %s "
                "WHERE id = %s AND or_monnaie >= %s RETURNING id",
                (cout_upgrade, joueur_id, cout_upgrade),
            )
            if cur.fetchone() is None:
                conn.rollback()
                flash("Crédits insuffisants.", "error")
                return redirect(url_for("forge.index"))

            # Consommation bois dans la même transaction
            if a_bois:
                consommer_materiaux(conn, joueur_id, {"bois_chene": 1})

        conn.commit()  # commit unique : amélioration + or + bois
        flash(f"✅ Équipement amélioré à +{amelioration + 1} !", "success")
    finally:
        conn.close()
    return redirect(url_for("forge.index"))
