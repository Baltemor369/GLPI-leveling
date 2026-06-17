"""Page Journal — historique de tous les tickets traités."""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app"))
import db_queries as db
import style
import psycopg2.extras
from auth import require_login, render_sidebar

st.set_page_config(page_title="Journal — GlpiLeveling", page_icon="📜", layout="wide")
style.inject(st)

require_login()
render_sidebar()

st.markdown("# &#x1F4DC; Journal des Aventures")
st.markdown("*Historique de tous les tickets traités par l'équipe*")
st.markdown("---")

conn = db.get_conn()
with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
    cur.execute("""
        SELECT t.ticket_id, j.username, t.xp_gagne, t.conforme,
               t.analyse_llm, t.date_traitement
        FROM tickets_traites t
        JOIN joueurs j ON j.id = t.joueur_id
        ORDER BY t.date_traitement DESC
        LIMIT 50
    """)
    tickets = [dict(r) for r in cur.fetchall()]
conn.close()

if not tickets:
    st.markdown("*Aucun ticket enregistré pour l'instant. Lance le worker !*")
    st.stop()

# Métriques globales
total = len(tickets)
conformes = sum(1 for t in tickets if t["conforme"])
xp_total = sum(t["xp_gagne"] for t in tickets)

c1, c2, c3 = st.columns(3)
c1.metric("Tickets traités", total)
c2.metric("Taux de conformité", f"{int(conformes/total*100)}%")
c3.metric("XP distribués", xp_total)

st.markdown("---")

for t in tickets:
    badge = '<span class="badge-conforme">✓ CONFORME</span>' if t["conforme"] else '<span class="badge-nonconforme">✗ NON CONFORME</span>'
    date_str = t["date_traitement"].strftime("%d/%m/%Y %H:%M") if t["date_traitement"] else "—"
    st.markdown(f"""
    <div class="ticket-row">
        <strong>Ticket #{t['ticket_id']}</strong> &nbsp;·&nbsp;
        <span style="color:#c9a84c">{t['username']}</span> &nbsp;·&nbsp;
        {badge} &nbsp;·&nbsp;
        <span style="color:#c9a84c">+{t['xp_gagne']} XP</span>
        <span style="float:right;color:#6b5a4e;font-size:0.8rem">{date_str}</span>
        <br><small style="color:#6b5a4e">{t['analyse_llm']}</small>
    </div>
    """, unsafe_allow_html=True)
