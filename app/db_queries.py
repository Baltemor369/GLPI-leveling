"""Requêtes PostgreSQL utilisées par l'interface Streamlit."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../sync"))

import psycopg2
import psycopg2.extras
from config import DATABASE_URL


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def tous_les_joueurs():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT j.id, j.username, j.level, j.xp, j.or_monnaie,
                       j.force_p, j.constitution_pv, j.agilite_vit, j.esprit_res,
                       j.points_a_attribuer,
                       COUNT(c.id) AS victoires
                FROM joueurs j
                LEFT JOIN combats c ON c.vainqueur_id = j.id AND c.statut = 'termine'
                GROUP BY j.id
                ORDER BY j.xp DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def get_joueur(joueur_id: int):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM joueurs WHERE id = %s", (joueur_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_equipements(joueur_id: int):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM equipements WHERE joueur_id = %s ORDER BY equipe DESC, id DESC",
                (joueur_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_tickets_joueur(joueur_id: int, limit: int = 20):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT ticket_id, xp_gagne, conforme, analyse_llm, date_traitement
                FROM tickets_traites
                WHERE joueur_id = %s
                ORDER BY date_traitement DESC
                LIMIT %s
            """, (joueur_id, limit))
            return [dict(r) for r in cur.fetchall()]


def depenser_point_stat(joueur_id: int, stat: str):
    """Dépense 1 point de stat disponible sur la statistique choisie."""
    colonnes_valides = {"force_p", "constitution_pv", "agilite_vit", "esprit_res"}
    if stat not in colonnes_valides:
        raise ValueError(f"Stat invalide : {stat}")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE joueurs
                SET points_a_attribuer = points_a_attribuer - 1,
                    {col} = {col} + 1
                WHERE id = %s AND points_a_attribuer > 0
                RETURNING points_a_attribuer
            """.format(col=stat), (joueur_id,))
            row = cur.fetchone()
        conn.commit()
    return row is not None
