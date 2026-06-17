import psycopg2
import psycopg2.extras

from config import DATABASE_URL

# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------

def get_conn():
    return psycopg2.connect(DATABASE_URL)


# ---------------------------------------------------------------------------
# Initialisation du schéma (idempotent)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS joueurs (
    id                  INTEGER PRIMARY KEY,
    username            VARCHAR(100) NOT NULL,
    level               INTEGER NOT NULL DEFAULT 1,
    xp                  INTEGER NOT NULL DEFAULT 0,
    or_monnaie          INTEGER NOT NULL DEFAULT 0,
    force_p             INTEGER NOT NULL DEFAULT 10,
    constitution_pv     INTEGER NOT NULL DEFAULT 10,
    agilite_vit         INTEGER NOT NULL DEFAULT 10,
    esprit_res          INTEGER NOT NULL DEFAULT 10,
    points_a_attribuer  INTEGER NOT NULL DEFAULT 0,
    pity_expedition     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS equipements (
    id              SERIAL PRIMARY KEY,
    joueur_id       INTEGER NOT NULL REFERENCES joueurs(id),
    nom             VARCHAR(100) NOT NULL,
    type            VARCHAR(10)  NOT NULL CHECK (type IN ('arme','armure','amul')),
    bonus_stat      VARCHAR(20)  NOT NULL,
    valeur_bonus    INTEGER NOT NULL DEFAULT 0,
    equipe          BOOLEAN NOT NULL DEFAULT FALSE,
    amelioration    INTEGER NOT NULL DEFAULT 0,
    passif_code     VARCHAR(30),
    cout_base       INTEGER NOT NULL DEFAULT 0,
    tier            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tickets_traites (
    ticket_id          INTEGER PRIMARY KEY,
    joueur_id          INTEGER NOT NULL REFERENCES joueurs(id),
    xp_gagne           INTEGER NOT NULL,
    score_difficulte   INTEGER NOT NULL DEFAULT 5,
    createur_id        INTEGER REFERENCES joueurs(id),
    xp_conformite      INTEGER NOT NULL DEFAULT 0,
    score_conformite   INTEGER NOT NULL DEFAULT 5,
    conforme           BOOLEAN NOT NULL DEFAULT TRUE,
    analyse_llm        TEXT,
    analyse_conformite TEXT,
    nom_categorie      VARCHAR(100),
    date_traitement    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    token       VARCHAR(36) PRIMARY KEY,
    joueur_id   INTEGER NOT NULL REFERENCES joueurs(id),
    username    VARCHAR(100) NOT NULL,
    expires     TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS expeditions (
    id          SERIAL PRIMARY KEY,
    joueur_id   INTEGER NOT NULL REFERENCES joueurs(id),
    debut       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fin         TIMESTAMPTZ NOT NULL,
    reclamee    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS materiaux_joueur (
    joueur_id       INTEGER NOT NULL REFERENCES joueurs(id),
    materiau_code   VARCHAR(30) NOT NULL,
    quantite        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (joueur_id, materiau_code)
);

CREATE TABLE IF NOT EXISTS badges (
    code        VARCHAR(50) PRIMARY KEY,
    nom         VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    icone       VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS joueur_badges (
    joueur_id   INTEGER NOT NULL REFERENCES joueurs(id),
    badge_code  VARCHAR(50) NOT NULL REFERENCES badges(code),
    date_obtenu TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (joueur_id, badge_code)
);

CREATE TABLE IF NOT EXISTS combats (
    id              SERIAL PRIMARY KEY,
    attaquant_id    INTEGER NOT NULL REFERENCES joueurs(id),
    defenseur_id    INTEGER NOT NULL REFERENCES joueurs(id),
    statut          VARCHAR(20) NOT NULL DEFAULT 'en_attente'
                        CHECK (statut IN ('en_attente','en_cours','termine')),
    tour_de_qui     INTEGER REFERENCES joueurs(id),
    pv_attaquant    INTEGER NOT NULL DEFAULT 0,
    pv_defenseur    INTEGER NOT NULL DEFAULT 0,
    mise            INTEGER NOT NULL DEFAULT 0,
    log_combat      TEXT NOT NULL DEFAULT '',
    vainqueur_id    INTEGER REFERENCES joueurs(id)
);
"""

# ---------------------------------------------------------------------------
# Migrations numérotées — chaque entrée ne s'exécute qu'une seule fois.
# Pour ajouter une évolution de schéma : append une nouvelle entrée.
# Ne jamais modifier une migration existante.
# ---------------------------------------------------------------------------
MIGRATIONS = [
    # 1 — colonnes ajoutées après la création initiale de combats
    """
    ALTER TABLE combats ADD COLUMN IF NOT EXISTS pv_attaquant INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE combats ADD COLUMN IF NOT EXISTS pv_defenseur INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE combats ADD COLUMN IF NOT EXISTS mise         INTEGER NOT NULL DEFAULT 0;
    """,
    # 2 — colonnes ajoutées à tickets_traites (conformité, LLM, catégorie)
    """
    ALTER TABLE tickets_traites ADD COLUMN IF NOT EXISTS score_difficulte   INTEGER NOT NULL DEFAULT 5;
    ALTER TABLE tickets_traites ADD COLUMN IF NOT EXISTS createur_id        INTEGER REFERENCES joueurs(id);
    ALTER TABLE tickets_traites ADD COLUMN IF NOT EXISTS xp_conformite      INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE tickets_traites ADD COLUMN IF NOT EXISTS score_conformite   INTEGER NOT NULL DEFAULT 5;
    ALTER TABLE tickets_traites ADD COLUMN IF NOT EXISTS analyse_conformite TEXT;
    ALTER TABLE tickets_traites ADD COLUMN IF NOT EXISTS nom_categorie      VARCHAR(100);
    """,
    # 3 — vainqueur_id sur combats + colonnes forge sur équipements + reclamee expéditions
    """
    ALTER TABLE combats      ADD COLUMN IF NOT EXISTS vainqueur_id  INTEGER REFERENCES joueurs(id);
    ALTER TABLE equipements  ADD COLUMN IF NOT EXISTS amelioration  INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE equipements  ADD COLUMN IF NOT EXISTS passif_code   VARCHAR(30);
    ALTER TABLE equipements  ADD COLUMN IF NOT EXISTS cout_base     INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE equipements  ADD COLUMN IF NOT EXISTS tier          INTEGER NOT NULL DEFAULT 1;
    ALTER TABLE expeditions  ADD COLUMN IF NOT EXISTS reclamee      BOOLEAN NOT NULL DEFAULT FALSE;
    """,
    # 4 — pity expéditions
    """
    ALTER TABLE joueurs ADD COLUMN IF NOT EXISTS pity_expedition INTEGER NOT NULL DEFAULT 0;
    """,
]


def _current_version(cur) -> int:
    cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
    return cur.fetchone()[0]


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            conn.commit()
            version = _current_version(cur)
            pending = MIGRATIONS[version:]
            for i, sql in enumerate(pending, start=version + 1):
                for statement in sql.strip().split(";"):
                    statement = statement.strip()
                    if statement:
                        cur.execute(statement)
                cur.execute(
                    "INSERT INTO schema_version (version) VALUES (%s)", (i,)
                )
                print(f"Migration {i} appliquée.")
            conn.commit()
        _seed_badges(conn)
    print(f"Base de données prête (version {version + len(pending)}).")


# ---------------------------------------------------------------------------
# Joueurs
# ---------------------------------------------------------------------------

# Seuils d'XP cumulatifs par niveau (niveau N = index N-1)
XP_PAR_NIVEAU = [0, 100, 250, 450, 700, 1000, 1400, 1900, 2500, 3200, 4000]

def xp_requis_pour_niveau(niveau: int) -> int:
    if niveau <= len(XP_PAR_NIVEAU):
        return XP_PAR_NIVEAU[niveau - 1]
    # Au-delà du tableau : progression quadratique
    return int(4000 + (niveau - len(XP_PAR_NIVEAU)) ** 2 * 200)


def get_or_create_joueur(conn, glpi_user_id: int, username: str):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM joueurs WHERE id = %s", (glpi_user_id,))
        joueur = cur.fetchone()
        if joueur is None:
            cur.execute(
                "INSERT INTO joueurs (id, username) VALUES (%s, %s) RETURNING *",
                (glpi_user_id, username),
            )
            joueur = cur.fetchone()
            conn.commit()
            print(f"Nouveau joueur créé : {username} (id={glpi_user_id})")
    return dict(joueur)


def ajouter_xp(conn, joueur_id: int, xp_gain: int):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "UPDATE joueurs SET xp = xp + %s WHERE id = %s RETURNING xp, level, points_a_attribuer",
            (xp_gain, joueur_id),
        )
        joueur = cur.fetchone()
        nouvelle_xp = joueur["xp"]
        niveau_actuel = joueur["level"]
        points = joueur["points_a_attribuer"]

        # Vérifier les montées de niveau
        niveaux_gagnes = 0
        while nouvelle_xp >= xp_requis_pour_niveau(niveau_actuel + 1):
            niveau_actuel += 1
            niveaux_gagnes += 1

        if niveaux_gagnes:
            points += niveaux_gagnes * 3  # 3 points de stats par niveau
            cur.execute(
                "UPDATE joueurs SET level = %s, points_a_attribuer = %s WHERE id = %s",
                (niveau_actuel, points, joueur_id),
            )

        conn.commit()
    return niveaux_gagnes, niveau_actuel


# ---------------------------------------------------------------------------
# Tickets traités
# ---------------------------------------------------------------------------

def ticket_deja_traite(conn, ticket_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM tickets_traites WHERE ticket_id = %s", (ticket_id,))
        return cur.fetchone() is not None


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------

_BADGES_SEED = [
    ("premiere_quete",  "Première Quête",      "Résoudre son 1er ticket",                               "🎯"),
    ("ecuyer",          "Écuyer",              "Résoudre 10 tickets",                                   "⚔️"),
    ("chevalier",       "Chevalier",           "Résoudre 50 tickets",                                   "🛡️"),
    ("paladin",         "Paladin",             "Résoudre 100 tickets",                                  "👑"),
    ("eclair",          "Éclair",              "Résoudre un ticket le jour même (rapidité max)",        "⚡"),
    ("maitre_serveurs", "Maître des Serveurs", "Résoudre 10 tickets catégorie Serveur",                 "🖥️"),
    ("plume_or",        "Plume d'Or",          "Créer un ticket avec score conformité 10/10",           "✒️"),
    ("scribe_parfait",  "Scribe Parfait",      "10 tickets créés avec score conformité ≥ 8",            "📜"),
    ("bapteme_feu",     "Baptême du Feu",      "Gagner son 1er combat en Arène",                       "🥊"),
    ("gladiateur",      "Gladiateur",          "Gagner 5 combats en Arène",                            "⚔️"),
    ("champion_arene",  "Champion de l'Arène", "Gagner 10 combats en Arène",                           "🏆"),
    ("insaisissable",   "Insaisissable",        "Esquiver 3 fois dans le même combat",                  "💨"),
    ("coup_de_grace",   "Coup de Grâce",       "Éliminer un adversaire avec un Coup Critique",         "💥"),
    ("parieur",         "Parieur",             "Gagner un combat avec une mise > 0",                    "🎲"),
    ("haut_risque",     "Haut Risque",         "Gagner un combat avec une mise ≥ 50 or",                "💰"),
    ("ascension",       "Ascension",           "Atteindre le niveau 5",                                 "🌟"),
    ("seigneur",        "Seigneur",            "Atteindre le niveau 10",                                "🔥"),
    ("legende",         "Légende",             "Atteindre le niveau 15",                                "🌌"),
    ("forgeron",        "Forgeron",            "Fabriquer son 1er équipement en Forge",                 "🔨"),
    ("arsenal_complet", "Arsenal Complet",     "Avoir arme + armure + amulette équipés simultanément",  "🧰"),
]


def _seed_badges(conn):
    with conn.cursor() as cur:
        for code, nom, desc, icone in _BADGES_SEED:
            cur.execute(
                """INSERT INTO badges (code, nom, description, icone)
                   VALUES (%s, %s, %s, %s) ON CONFLICT (code) DO NOTHING""",
                (code, nom, desc, icone),
            )
    conn.commit()


def badge_deja_obtenu(conn, joueur_id: int, code: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM joueur_badges WHERE joueur_id = %s AND badge_code = %s",
            (joueur_id, code),
        )
        return cur.fetchone() is not None


def attribuer_badge(conn, joueur_id: int, code: str) -> bool:
    """Retourne True si le badge vient d'être attribué (pas déjà obtenu)."""
    if badge_deja_obtenu(conn, joueur_id, code):
        return False
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO joueur_badges (joueur_id, badge_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (joueur_id, code),
        )
    conn.commit()
    return True


def get_badges_joueur(conn, joueur_id: int) -> list:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT b.code, b.nom, b.description, b.icone, jb.date_obtenu
            FROM badges b
            LEFT JOIN joueur_badges jb
                   ON jb.badge_code = b.code AND jb.joueur_id = %s
            ORDER BY jb.date_obtenu ASC NULLS LAST, b.code
        """, (joueur_id,))
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Tickets traités
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Expéditions
# ---------------------------------------------------------------------------

def get_expedition_active(conn, joueur_id: int) -> dict | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM expeditions
            WHERE joueur_id = %s AND reclamee = FALSE
            ORDER BY id DESC LIMIT 1
        """, (joueur_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def lancer_expedition(conn, joueur_id: int, duree_heures: int) -> int:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO expeditions (joueur_id, fin)
            VALUES (%s, NOW() + INTERVAL '%s hours') RETURNING id
        """, (joueur_id, duree_heures))
        exp_id = cur.fetchone()[0]
    conn.commit()
    return exp_id


def marquer_reclamee(conn, expedition_id: int):
    with conn.cursor() as cur:
        cur.execute("UPDATE expeditions SET reclamee = TRUE WHERE id = %s", (expedition_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Matériaux
# ---------------------------------------------------------------------------

def get_materiaux(conn, joueur_id: int) -> dict:
    """Retourne {code: quantite} pour tous les matériaux du joueur."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT materiau_code, quantite FROM materiaux_joueur WHERE joueur_id = %s",
            (joueur_id,)
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def ajouter_materiau(conn, joueur_id: int, code: str, quantite: int):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO materiaux_joueur (joueur_id, materiau_code, quantite)
            VALUES (%s, %s, %s)
            ON CONFLICT (joueur_id, materiau_code)
            DO UPDATE SET quantite = materiaux_joueur.quantite + EXCLUDED.quantite
        """, (joueur_id, code, quantite))
    conn.commit()


def consommer_materiaux(conn, joueur_id: int, materiaux: dict) -> bool:
    """Consomme les matériaux si le joueur en a assez. Retourne True si succès."""
    stock = get_materiaux(conn, joueur_id)
    for code, qty in materiaux.items():
        if stock.get(code, 0) < qty:
            return False
    with conn.cursor() as cur:
        for code, qty in materiaux.items():
            cur.execute("""
                UPDATE materiaux_joueur SET quantite = quantite - %s
                WHERE joueur_id = %s AND materiau_code = %s
            """, (qty, joueur_id, code))
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Tickets traités
# ---------------------------------------------------------------------------

def enregistrer_ticket(conn, ticket_id: int, joueur_id: int, xp_gagne: int,
                       score_difficulte: int, analyse_llm: str,
                       createur_id: int | None, xp_conformite: int,
                       score_conformite: int, analyse_conformite: str,
                       nom_categorie: str = ""):
    conforme = score_conformite >= 6
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO tickets_traites
               (ticket_id, joueur_id, xp_gagne, score_difficulte, analyse_llm,
                createur_id, xp_conformite, score_conformite, conforme, analyse_conformite,
                nom_categorie)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (ticket_id, joueur_id, xp_gagne, score_difficulte, analyse_llm,
             createur_id, xp_conformite, score_conformite, conforme, analyse_conformite,
             nom_categorie),
        )
    conn.commit()
