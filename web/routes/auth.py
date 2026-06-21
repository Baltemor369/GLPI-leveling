from flask import Blueprint, session, redirect, url_for, request, render_template, flash
from ..auth import login_glpi

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "joueur_id" in session:
        return redirect(url_for("aventurier.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Remplis les deux champs.", "error")
            return render_template("login.html")

        result = login_glpi(username, password)

        if result is None:
            flash("Identifiants GLPI incorrects.", "error")
        elif result["glpi_id"] is None:
            flash(
                "Connexion GLPI réussie, mais aucun ticket ne t'est encore assigné. "
                "Ton profil sera créé dès ton premier ticket pris en charge.",
                "warning",
            )
        else:
            session["joueur_id"] = result["glpi_id"]
            session["username"] = result["username"]
            return redirect(url_for("aventurier.index"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
