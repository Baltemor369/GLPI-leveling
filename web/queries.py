"""Couche d'accès BDD pour le frontend Flask (lecture + écriture légère)."""

import psycopg2
import psycopg2.extras
from config import DATABASE_URL


def _conn():
    """Open a new psycopg2 connection from DATABASE_URL."""
    return psycopg2.connect(DATABASE_URL)


def tous_les_joueurs() -> list[dict]:
    """Return all players ordered by XP descending, including their win count."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT j.id, j.username, j.level, j.xp, j.or_monnaie,
                       j.force_p, j.constitution_pv, j.agilite_vit, j.esprit_res,
                       j.points_a_attribuer, j.points_combat,
                       COUNT(c.id) AS victoires
                FROM joueurs j
                LEFT JOIN combats c ON c.vainqueur_id = j.id AND c.statut = 'termine'
                GROUP BY j.id
                ORDER BY j.xp DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def tous_les_joueurs_par_pc() -> list[dict]:
    """Return all players ordered by points_combat descending."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT j.id, j.username, j.level, j.xp, j.or_monnaie,
                       j.force_p, j.constitution_pv, j.agilite_vit, j.esprit_res,
                       j.points_a_attribuer, j.points_combat,
                       COUNT(c.id) AS victoires
                FROM joueurs j
                LEFT JOIN combats c ON c.vainqueur_id = j.id AND c.statut = 'termine'
                GROUP BY j.id
                ORDER BY j.points_combat DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def get_joueur(joueur_id: int) -> dict | None:
    """Return a single player row by primary key, or None if not found."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM joueurs WHERE id = %s", (joueur_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_equipements(joueur_id: int) -> list[dict]:
    """Return the player's equipment sorted by equipped status then insertion order."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM equipements WHERE joueur_id = %s ORDER BY equipe DESC, id DESC",
                (joueur_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_tickets_joueur(joueur_id: int, limit: int = 20) -> list[dict]:
    """Return the most recent processed tickets for one player (default 20)."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT ticket_id, xp_gagne, conforme, analyse_llm, date_traitement
                FROM tickets_traites
                WHERE joueur_id = %s
                ORDER BY date_traitement DESC
                LIMIT %s
            """, (joueur_id, limit))
            return [dict(r) for r in cur.fetchall()]


def get_tickets_tous(limit: int = 50) -> list[dict]:
    """Return the most recent processed tickets across all players (default 50)."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT t.ticket_id, j.username, t.xp_gagne, t.conforme,
                       t.analyse_llm, t.date_traitement
                FROM tickets_traites t
                JOIN joueurs j ON j.id = t.joueur_id
                ORDER BY t.date_traitement DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]


def get_saison_courante() -> dict | None:
    """Return all columns of the current active season row, or None if no season exists."""
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM saisons WHERE statut = 'en_cours' ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            return dict(row) if row else None


def depenser_point_stat(joueur_id: int, stat: str) -> bool:
    """Spend one unallocated stat point on the given stat; return False if none available.

    Raises ValueError for an invalid stat name to prevent SQL injection via the
    column name, which cannot be parameterised with %s.
    """
    colonnes_valides = {"force_p", "constitution_pv", "agilite_vit", "esprit_res"}
    if stat not in colonnes_valides:
        raise ValueError(f"Stat invalide : {stat}")
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE joueurs
                    SET points_a_attribuer = points_a_attribuer - 1,
                        {stat} = {stat} + 1
                    WHERE id = %s AND points_a_attribuer > 0
                    RETURNING id""",
                (joueur_id,),
            )
            row = cur.fetchone()
        conn.commit()
    return row is not None
