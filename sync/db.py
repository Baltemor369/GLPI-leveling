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
    pity_expedition     INTEGER NOT NULL DEFAULT 0,
    points_combat       INTEGER NOT NULL DEFAULT 1000
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
    vainqueur_id    INTEGER REFERENCES joueurs(id),
    cree_a          TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
    # 5 — points de combat Elo (initialisés à 1000 pour tous)
    """
    ALTER TABLE joueurs ADD COLUMN IF NOT EXISTS points_combat INTEGER NOT NULL DEFAULT 1000;
    """,
    # 6 — saisons et archives de fin de saison
    """
    CREATE TABLE IF NOT EXISTS saisons (
        id      SERIAL PRIMARY KEY,
        numero  INTEGER NOT NULL,
        debut   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        fin     TIMESTAMPTZ,
        statut  VARCHAR(20) NOT NULL DEFAULT 'en_cours'
                CHECK (statut IN ('en_cours','termine'))
    );
    CREATE TABLE IF NOT EXISTS saison_archives (
        id               SERIAL PRIMARY KEY,
        saison_id        INTEGER NOT NULL REFERENCES saisons(id),
        joueur_id        INTEGER NOT NULL REFERENCES joueurs(id),
        rang_xp          INTEGER NOT NULL DEFAULT 0,
        rang_pc          INTEGER NOT NULL DEFAULT 0,
        xp_final         INTEGER NOT NULL DEFAULT 0,
        pc_final         INTEGER NOT NULL DEFAULT 1000,
        victoires_final  INTEGER NOT NULL DEFAULT 0,
        level_final      INTEGER NOT NULL DEFAULT 1,
        enregistre_a     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    # 7 — timestamp de création sur combats (victoires scopées par saison).
    # Les lignes existantes reçoivent NOW() à la migration — acceptable pour la 1re clôture.
    """
    ALTER TABLE combats ADD COLUMN IF NOT EXISTS cree_a TIMESTAMPTZ NOT NULL DEFAULT NOW();
    """,
    # 8 — unicité partielle : enforce qu'une seule saison peut être 'en_cours'
    # simultanément. L'index filtre uniquement les lignes 'en_cours', donc les
    # saisons 'termine' ne sont pas contraintes.
    # Travaille de pair avec le FOR UPDATE et la garde rowcount de
    # archiver_et_reset_saison pour empêcher tout double-reset.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS saisons_unique_en_cours
        ON saisons (statut) WHERE statut = 'en_cours';
    """,
    # 9 — re-thématisation informatique : renomme les équipements déjà en base
    # (thème médiéval → composants matériels). Les colonnes internes
    # (type, bonus_stat, passif_code, tier) restent inchangées.
    """
    UPDATE equipements SET nom = 'Pentium I'         WHERE nom = 'Épée en Fer';
    UPDATE equipements SET nom = 'Core i3'           WHERE nom = 'Lame d''Acier';
    UPDATE equipements SET nom = 'Core i5'           WHERE nom = 'Épée de Mithril';
    UPDATE equipements SET nom = 'Core i7'           WHERE nom = 'Lame Runique';
    UPDATE equipements SET nom = 'CPU Quantique'     WHERE nom = 'Épée du Néant';
    UPDATE equipements SET nom = 'Pare-feu basique'  WHERE nom = 'Tunique de Cuir';
    UPDATE equipements SET nom = 'Antivirus'         WHERE nom = 'Cotte de Mailles';
    UPDATE equipements SET nom = 'Chiffrement AES'   WHERE nom = 'Armure de Plates';
    UPDATE equipements SET nom = 'IDS/IPS'           WHERE nom = 'Armure Runique';
    UPDATE equipements SET nom = 'Zero Trust'        WHERE nom = 'Armure du Néant';
    UPDATE equipements SET nom = 'Barrette RAM'      WHERE nom = 'Amulette de Vitalité';
    UPDATE equipements SET nom = 'Carte réseau'      WHERE nom = 'Bague de Célérité';
    UPDATE equipements SET nom = 'SSD NVMe'          WHERE nom = 'Pendentif de l''Aube';
    UPDATE equipements SET nom = 'Fibre optique'     WHERE nom = 'Talisman Runique';
    UPDATE equipements SET nom = 'Cœur IA'           WHERE nom = 'Orbe du Néant';
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
    ("premiere_quete",  "Hello World",         "Résoudre son 1er ticket",                               "🎯"),
    ("ecuyer",          "Stagiaire",           "Résoudre 10 tickets",                                   "🐣"),
    ("chevalier",       "Technicien",          "Résoudre 50 tickets",                                   "🔧"),
    ("paladin",         "Ingénieur Système",   "Résoudre 100 tickets",                                  "🧑‍💻"),
    ("eclair",          "Hotfix",              "Résoudre un ticket le jour même (rapidité max)",        "⚡"),
    ("maitre_serveurs", "Maître des Serveurs", "Résoudre 10 tickets catégorie Serveur",                 "🖥️"),
    ("plume_or",        "Doc Parfaite",        "Créer un ticket avec score conformité 10/10",           "📝"),
    ("scribe_parfait",  "Rédacteur Technique", "10 tickets créés avec score conformité ≥ 8",            "📄"),
    ("bapteme_feu",     "Premier Benchmark",   "Gagner son 1er duel au Benchmark",                     "🥊"),
    ("gladiateur",      "Challenger",          "Gagner 5 duels au Benchmark",                          "⚔️"),
    ("champion_arene",  "Champion Benchmark",  "Gagner 10 duels au Benchmark",                         "🏆"),
    ("insaisissable",   "Low Latency",          "Esquiver 3 fois dans le même duel",                    "💨"),
    ("coup_de_grace",   "Kill -9",             "Éliminer un adversaire avec un Coup Critique",         "💥"),
    ("parieur",         "Parieur",             "Gagner un duel avec une mise > 0",                      "🎲"),
    ("haut_risque",     "All-In",              "Gagner un duel avec une mise ≥ 50 crédits",             "💰"),
    ("ascension",       "Montée en charge",    "Atteindre le niveau 5",                                 "🌟"),
    ("seigneur",        "Senior",              "Atteindre le niveau 10",                                "🔥"),
    ("legende",         "10x Engineer",        "Atteindre le niveau 15",                                "🌌"),
    ("forgeron",           "Assembleur",           "Assembler son 1er composant à l'Atelier",                  "🔧"),
    ("arsenal_complet",    "Setup Complet",        "Avoir processeur + sécurité + module équipés simultanément","🧰"),
    ("artisan",            "Overclockeur",         "Améliorer un composant à +5",                              "⚙️"),
    ("grand_maitre_forge", "Maître Assembleur",    "Assembler un composant Tier 5",                            "🌟"),
    ("set_legendaire",     "Config Ultime",        "Équiper processeur + sécurité + module tous en Tier 5",   "💎"),
    ("perfection_absolue", "Build Parfait",        "Processeur + sécurité + module Tier 5 tous améliorés à +20","👑"),
    ("explorateur",        "Premier Scan",         "Compléter son 1er scan réseau",                           "📡"),
    ("routard",            "Crawler",              "Compléter 10 scans réseau",                               "🌍"),
    ("chasseur_tresors",   "Chasseur de Qubits",   "Rapporter un Qubit d'un scan réseau",                     "⚛️"),
    ("invaincu",           "Uptime 100%",          "Remporter 3 duels consécutifs",                           "🔥"),
    ("sans_pitie",         "No Mercy",             "Gagner un duel sans jamais utiliser Repos",               "💀"),
    ("stakhanoviste",      "Batch Processor",      "Résoudre 5 tickets dans la même journée",                 "📋"),
    ("saison_champion_xp", "Champion de Saison",   "Terminer 1er au classement XP d'une saison",             "👑"),
    ("saison_champion_pc", "Champion Benchmark de Saison", "Terminer 1er au classement Benchmark d'une saison","🏆"),
    ("saison_podium",      "Podium de Saison",      "Figurer dans le top 3 d'un classement saisonnier",       "🎖️"),
]


def _seed_badges(conn):
    """Insère ou met à jour les badges de référence.

    L'UPSERT garantit que le renommage d'un badge (nom/description/icône) se
    propage aux badges déjà débloqués sans casser les clés étrangères
    (`joueur_badges.badge_code` référence `code`, qui reste immuable).
    """
    with conn.cursor() as cur:
        for code, nom, desc, icone in _BADGES_SEED:
            cur.execute(
                """INSERT INTO badges (code, nom, description, icone)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (code) DO UPDATE
                       SET nom         = EXCLUDED.nom,
                           description = EXCLUDED.description,
                           icone       = EXCLUDED.icone""",
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
            VALUES (%s, NOW() + make_interval(hours => %s)) RETURNING id
        """, (joueur_id, duree_heures))
        exp_id = cur.fetchone()[0]
    conn.commit()
    return exp_id


def marquer_reclamee(conn, expedition_id: int) -> bool:
    """Retourne False si l'expédition était déjà réclamée (garde anti-double-claim).
    Ne commit pas — le caller gère la transaction."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE expeditions SET reclamee = TRUE WHERE id = %s AND reclamee = FALSE",
            (expedition_id,),
        )
        return cur.rowcount == 1


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
    """Ne commit pas — le caller gère la transaction."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO materiaux_joueur (joueur_id, materiau_code, quantite)
            VALUES (%s, %s, %s)
            ON CONFLICT (joueur_id, materiau_code)
            DO UPDATE SET quantite = materiaux_joueur.quantite + EXCLUDED.quantite
        """, (joueur_id, code, quantite))


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
# Saisons
# ---------------------------------------------------------------------------

def get_saison_courante(conn) -> dict | None:
    """Return the current active season row as a dict, or None if no season exists yet.

    The unique partial index on saisons(statut) WHERE statut='en_cours' guarantees
    at most one row is returned; ORDER BY id DESC is a safety fallback only.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM saisons WHERE statut = 'en_cours' ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return dict(row) if row else None


def init_saison_si_absente(conn) -> bool:
    """Crée la saison 1 si aucune saison n'existe (INSERT atomique, pas de race condition).
    Retourne True si la saison 1 vient d'être créée."""
    with conn.cursor() as cur:
        cur.execute("INSERT INTO saisons (numero) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM saisons)")
        created = cur.rowcount == 1
    if created:
        conn.commit()
    return created


def archiver_et_reset_saison(conn) -> list[dict]:
    """Archive les stats de fin de saison, remet tous les joueurs à zéro,
    clôt la saison courante et crée la suivante.

    Garanties transactionnelles :
    - SELECT … FOR UPDATE verrouille la ligne de saison dès le début, bloquant
      toute exécution concurrente (relance rapide du worker, intervention manuelle).
    - La garde ``AND statut='en_cours'`` sur l'UPDATE final vérifie rowcount == 1 ;
      si la saison avait déjà été clôturée par un autre process, rowcount == 0 et
      une RuntimeError est levée pour annuler toute la transaction.
    - Les badges saison sont insérés via INSERT … ON CONFLICT DO NOTHING dans
      la même transaction que l'archivage et le reset, garantissant leur atomicité.
      (L'appel passe en direct sans passer par attribuer_badge, qui commit seul.)

    Retourne la liste des archives (avec rangs rang_xp / rang_pc) de la saison close.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # FOR UPDATE : verrouille la ligne pour éviter un double-reset concurrent
        # (cas de relance rapide du worker ou intervention manuelle).
        cur.execute(
            "SELECT * FROM saisons WHERE statut = 'en_cours' ORDER BY id DESC LIMIT 1 FOR UPDATE"
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("archiver_et_reset_saison appelé sans saison en cours")
        saison    = dict(row)
        saison_id = saison["id"]
        numero    = saison["numero"]
        debut     = saison["debut"]

        # Classement final de la saison.
        # On ne compte que les combats gagnés DEPUIS le début de la saison
        # (c.cree_a >= debut), pour que les victoires soient scopées à la saison.
        # Deux classements indépendants : rang_xp (par XP) et rang_pc (par points
        # de combat), chacun calculé via RANK() sur l'ensemble des joueurs.
        cur.execute("""
            SELECT j.id AS joueur_id, j.xp, j.points_combat, j.level,
                   COUNT(c.id) AS victoires,
                   RANK() OVER (ORDER BY j.xp DESC)            AS rang_xp,
                   RANK() OVER (ORDER BY j.points_combat DESC) AS rang_pc
            FROM joueurs j
            LEFT JOIN combats c ON c.vainqueur_id = j.id
                                AND c.statut = 'termine'
                                AND c.cree_a >= %s
            GROUP BY j.id, j.xp, j.points_combat, j.level
        """, (debut,))
        resultats = [dict(r) for r in cur.fetchall()]

        for r in resultats:
            cur.execute("""
                INSERT INTO saison_archives
                    (saison_id, joueur_id, rang_xp, rang_pc,
                     xp_final, pc_final, victoires_final, level_final)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (saison_id, r["joueur_id"], r["rang_xp"], r["rang_pc"],
                  r["xp"], r["points_combat"], r["victoires"], r["level"]))

        # Badges saison, dans la MÊME transaction que l'archivage et le reset.
        # On insère en direct (sans passer par attribuer_badge, qui commit) afin de
        # préserver l'atomicité. ON CONFLICT DO NOTHING = idempotent si rejoué.
        def _attribuer_badge_saison(joueur_id: int, badge_code: str):
            cur.execute(
                "INSERT INTO joueur_badges (joueur_id, badge_code) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (joueur_id, badge_code),
            )

        for r in resultats:
            joueur_id = r["joueur_id"]
            if r["rang_xp"] == 1:
                _attribuer_badge_saison(joueur_id, "saison_champion_xp")
            if r["rang_pc"] == 1:
                _attribuer_badge_saison(joueur_id, "saison_champion_pc")
            if r["rang_xp"] <= 3 or r["rang_pc"] <= 3:
                _attribuer_badge_saison(joueur_id, "saison_podium")

        # Annuler les combats et expéditions actifs
        cur.execute("UPDATE combats     SET statut   = 'termine' WHERE statut IN ('en_attente','en_cours')")
        cur.execute("UPDATE expeditions SET reclamee = TRUE      WHERE reclamee = FALSE")

        # Remettre les joueurs à zéro
        cur.execute("""
            UPDATE joueurs SET
                xp = 0, level = 1,
                force_p = 10, constitution_pv = 10, agilite_vit = 10, esprit_res = 10,
                points_a_attribuer = 0, or_monnaie = 50,
                points_combat = 1000, pity_expedition = 0
        """)

        # Supprimer équipements et matériaux
        cur.execute("DELETE FROM equipements")
        cur.execute("DELETE FROM materiaux_joueur")

        # Clôturer la saison — la condition AND statut='en_cours' est la garde finale
        # contre un double-reset : si la saison est déjà 'termine', rowcount == 0.
        cur.execute(
            "UPDATE saisons SET statut = 'termine', fin = NOW() WHERE id = %s AND statut = 'en_cours'",
            (saison_id,),
        )
        if cur.rowcount != 1:
            raise RuntimeError(f"Saison {saison_id} déjà clôturée — reset annulé (double-reset évité)")
        cur.execute("INSERT INTO saisons (numero) VALUES (%s)", (numero + 1,))

    conn.commit()
    return resultats


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
