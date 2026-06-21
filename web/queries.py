"""Couche d'accès BDD pour le frontend Flask (lecture + écriture légère)."""

import psycopg2
import psycopg2.extras
from config import DATABASE_URL


def _conn():
    return psycopg2.connect(DATABASE_URL)


def tous_les_joueurs() -> list[dict]:
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


def get_joueur(joueur_id: int) -> dict | None:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM joueurs WHERE id = %s", (joueur_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_equipements(joueur_id: int) -> list[dict]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM equipements WHERE joueur_id = %s ORDER BY equipe DESC, id DESC",
                (joueur_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_tickets_joueur(joueur_id: int, limit: int = 20) -> list[dict]:
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


def depenser_point_stat(joueur_id: int, stat: str) -> bool:
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
