# -*- coding: utf-8 -*-
"""CSS RPG médiéval immersif — GlpiLeveling."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap');

/* ── Variables ─────────────────────────────────── */
:root {
    --or:         #c9a84c;
    --or-clair:   #e8c96a;
    --or-sombre:  #8a6a1a;
    --rouge:      #8b1a1a;
    --parchemin:  #f0ddb0;
    --brun:       #2c1810;
    --brun2:      #3d2314;
    --brun3:      #1a0d06;
    --gris:       #7a6a55;
    --vert:       #2a5a2a;
}

/* ── Masquer l'interface Streamlit native ─────────── */
#MainMenu                              { visibility: hidden !important; }
footer                                 { visibility: hidden !important; }
[data-testid="stToolbar"]             { display: none !important; }
[data-testid="stDecoration"]          { display: none !important; }
[data-testid="stStatusWidget"]        { display: none !important; }

/* Bouton "Deploy" visible en haut à droite */
.stDeployButton, [data-testid="stBaseButton-headerNoPadding"] { display: none !important; }

/* Header blanc : collapse complet — hauteur 0, fond brun, overflow caché */
[data-testid="stHeader"] {
    background-color: var(--brun) !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    overflow: hidden !important;
    border: none !important;
    box-shadow: none !important;
}

/* Compenser le padding-top que Streamlit ajoute à cause du header */
[data-testid="stMainBlockContainer"],
[data-testid="block-container"] {
    padding-top: 1.5rem !important;
}

/* ── Base globale ───────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background-color: var(--brun) !important;
    color: var(--parchemin) !important;
    font-family: 'Crimson Text', Georgia, serif !important;
}

/* ── Sidebar ─────────────────────────────────────── */
/* NOTE : Streamlit utilise <section> (pas <div>) pour la sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--brun3) 0%, var(--brun2) 100%) !important;
    border-right: 2px solid var(--or-sombre) !important;
    box-shadow: 4px 0 12px rgba(0,0,0,0.6) !important;
}

/* Tout le texte de la sidebar — sélecteur le plus large possible */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] a,
section[data-testid="stSidebar"] li,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div {
    color: var(--parchemin) !important;
    opacity: 1 !important;
    visibility: visible !important;
}

/* Liens de navigation */
[data-testid="stSidebarNavLink"] {
    border-radius: 4px !important;
    padding: 8px 12px !important;
}
[data-testid="stSidebarNavLink"]:hover {
    background: rgba(201,168,76,0.12) !important;
}
[data-testid="stSidebarNavLink"]:hover *  { color: var(--or) !important; }
[data-testid="stSidebarNavLink"][aria-selected="true"] {
    background: rgba(201,168,76,0.2) !important;
    border-left: 3px solid var(--or) !important;
}
[data-testid="stSidebarNavLink"][aria-selected="true"] * { color: var(--or) !important; }

/* Fix dropdown selectbox — fond sombre */
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {
    background-color: var(--brun2) !important;
    border: 1px solid var(--or-sombre) !important;
}
[data-testid="stSelectbox"] svg { color: var(--or) !important; }
[data-baseweb="select"] *       { color: var(--parchemin) !important; }
[data-baseweb="popover"] *      { background: var(--brun2) !important; color: var(--parchemin) !important; }

/* ── Titres ─────────────────────────────────────── */
h1, h2, h3, h4 {
    font-family: 'Cinzel', serif !important;
    color: var(--or) !important;
    text-shadow: 0 0 8px rgba(201,168,76,0.4),
                 1px 2px 6px rgba(0,0,0,0.9) !important;
    letter-spacing: 1px !important;
}
h1 { font-size: 2.4rem !important; border-bottom: 1px solid var(--or-sombre); padding-bottom: 8px; }
h2 { font-size: 1.6rem !important; }
h3 { font-size: 1.2rem !important; }

/* ── Cartes de stats ─────────────────────────────── */
.stat-card {
    background:
        linear-gradient(135deg, rgba(61,35,20,0.95) 0%, rgba(26,13,6,0.95) 100%);
    border: 1px solid var(--or-sombre);
    box-shadow:
        0 0 0 1px var(--brun3),
        inset 0 1px 0 rgba(201,168,76,0.2),
        0 4px 16px rgba(0,0,0,0.6),
        0 0 20px rgba(201,168,76,0.05);
    border-radius: 6px;
    padding: 16px 12px;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.stat-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--or), transparent);
}
.stat-card::after {
    content: '';
    position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--or-sombre), transparent);
}
.stat-label {
    color: var(--gris);
    font-size: 0.7rem;
    font-family: 'Cinzel', serif;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.stat-value {
    color: var(--or-clair);
    font-size: 2rem;
    font-weight: 700;
    font-family: 'Cinzel', serif;
    text-shadow: 0 0 10px rgba(201,168,76,0.5);
}
.stat-desc {
    color: var(--gris);
    font-size: 0.72rem;
    margin-top: 6px;
    font-style: italic;
}

/* ── Barre XP ────────────────────────────────────── */
.xp-bar-bg {
    background: var(--brun3);
    border: 1px solid var(--or-sombre);
    border-radius: 8px;
    height: 26px;
    width: 100%;
    overflow: hidden;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.8), 0 0 8px rgba(201,168,76,0.1);
}
.xp-bar-fill {
    background: linear-gradient(90deg, var(--rouge) 0%, #c47a1a 60%, var(--or) 100%);
    height: 100%;
    border-radius: 8px;
    box-shadow: 0 0 8px rgba(201,168,76,0.6);
    transition: width 0.6s ease;
}
.xp-label {
    text-align: center;
    color: var(--gris);
    font-size: 0.82rem;
    margin-top: 5px;
    font-family: 'Crimson Text', serif;
    letter-spacing: 0.5px;
}

/* ── Divider orné ────────────────────────────────── */
.ornement {
    text-align: center;
    color: var(--or-sombre);
    font-size: 1.2rem;
    margin: 8px 0;
    opacity: 0.7;
}

/* ── Badges conformité ───────────────────────────── */
.badge-conforme {
    background: rgba(42,90,42,0.4);
    color: #7fbf7f;
    border: 1px solid #4a8a4a;
    border-radius: 3px;
    padding: 2px 10px;
    font-size: 0.78rem;
    font-family: 'Cinzel', serif;
    letter-spacing: 1px;
}
.badge-nonconforme {
    background: rgba(90,20,20,0.4);
    color: #c07070;
    border: 1px solid #7a3030;
    border-radius: 3px;
    padding: 2px 10px;
    font-size: 0.78rem;
    font-family: 'Cinzel', serif;
    letter-spacing: 1px;
}

/* ── Ligne de ticket ──────────────────────────────── */
.ticket-row {
    background: linear-gradient(90deg, rgba(61,35,20,0.8), rgba(26,13,6,0.6));
    border-left: 3px solid var(--or-sombre);
    border-radius: 0 4px 4px 0;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-family: 'Crimson Text', serif;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
    transition: border-left-color 0.2s;
}
.ticket-row:hover { border-left-color: var(--or); }

/* ── Inputs texte & formulaires ──────────────────── */
[data-testid="stTextInput"] label,
[data-testid="stTextInput"] p {
    color: var(--parchemin) !important;
    font-family: 'Cinzel', serif !important;
    font-size: 0.78rem !important;
    letter-spacing: 1px !important;
}
[data-testid="stTextInput"] input {
    background-color: var(--brun2) !important;
    color: var(--parchemin) !important;
    border: 1px solid var(--or-sombre) !important;
    border-radius: 3px !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: var(--or) !important;
    box-shadow: 0 0 0 1px var(--or-sombre) !important;
}
[data-testid="stTextInput"] input::placeholder {
    color: var(--gris) !important;
}

/* Bouton de soumission de formulaire */
[data-testid="stFormSubmitButton"] button {
    background: linear-gradient(135deg, #5c1010, var(--rouge)) !important;
    color: var(--or-clair) !important;
    border: 1px solid var(--or-sombre) !important;
    font-family: 'Cinzel', serif !important;
    font-size: 0.78rem !important;
    letter-spacing: 1px !important;
    border-radius: 3px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.5) !important;
}
[data-testid="stFormSubmitButton"] button:hover {
    background: linear-gradient(135deg, var(--rouge), #a02020) !important;
    box-shadow: 0 0 10px rgba(201,168,76,0.3) !important;
}

/* ── Boutons ─────────────────────────────────────── */
div[data-testid="stButton"] button {
    background: linear-gradient(135deg, #5c1010, var(--rouge)) !important;
    color: var(--or-clair) !important;
    border: 1px solid var(--or-sombre) !important;
    font-family: 'Cinzel', serif !important;
    font-size: 0.78rem !important;
    letter-spacing: 1px !important;
    border-radius: 3px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05) !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] button:hover {
    background: linear-gradient(135deg, var(--rouge), #a02020) !important;
    box-shadow: 0 0 10px rgba(201,168,76,0.3), 0 2px 6px rgba(0,0,0,0.5) !important;
}

/* ── Métriques ───────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--brun2) !important;
    border: 1px solid var(--or-sombre) !important;
    border-radius: 6px !important;
    padding: 12px !important;
}
[data-testid="stMetricLabel"] { color: var(--gris) !important; font-family: 'Cinzel', serif !important; font-size: 0.75rem !important; }
[data-testid="stMetricValue"] { color: var(--or-clair) !important; font-family: 'Cinzel', serif !important; }

/* ── Classement ──────────────────────────────────── */
.rank-1 { color: #ffd700; text-shadow: 0 0 6px rgba(255,215,0,0.5); }
.rank-2 { color: #c0c0c0; text-shadow: 0 0 4px rgba(192,192,192,0.4); }
.rank-3 { color: #cd7f32; text-shadow: 0 0 4px rgba(205,127,50,0.4); }
.rank-row {
    background: linear-gradient(90deg, rgba(61,35,20,0.6), transparent);
    border-left: 2px solid var(--or-sombre);
    padding: 10px 14px;
    margin-bottom: 4px;
    border-radius: 0 4px 4px 0;
}

/* ── Info / Warning ──────────────────────────────── */
[data-testid="stAlert"] {
    background: rgba(61,35,20,0.8) !important;
    border: 1px solid var(--or-sombre) !important;
    color: var(--parchemin) !important;
    border-radius: 4px !important;
}

/* ── Séparateurs ─────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid var(--or-sombre) !important;
    margin: 16px 0 !important;
    opacity: 0.5 !important;
}

/* ── Fond sombre immédiat (avant injection du CSS Streamlit) ──── */
/* Évite le flash blanc au changement de page */
html, body { background-color: #2c1810 !important; }

/* ── Transition de page : fade-in du contenu ─────────────────── */
@keyframes glpi-page-in {
    from { opacity: 0; transform: translateY(5px); }
    to   { opacity: 1; transform: translateY(0);   }
}
[data-testid="stMainBlockContainer"] {
    animation: glpi-page-in 0.3s ease-out;
}

/* ── Spinner "Vérification des parchemins" ───────────────────── */
/* Forcer l'animation à tourner (certains !important dans le CSS peuvent la bloquer) */
[data-testid="stSpinner"] * {
    animation-play-state: running !important;
}
/* Texte du spinner */
[data-testid="stSpinner"] p,
[data-testid="stSpinner"] span {
    color: var(--or) !important;
    font-family: 'Cinzel', serif !important;
    font-size: 0.85rem !important;
    letter-spacing: 1px !important;
}
/* Roue SVG */
[data-testid="stSpinner"] svg {
    stroke: var(--or) !important;
}
/* Fallback border-spinner (versions Streamlit plus anciennes) */
[data-testid="stSpinner"] > div > div {
    border-color: var(--or-sombre) !important;
    border-top-color: var(--or) !important;
}
</style>
"""

def inject(st):
    st.markdown(CSS, unsafe_allow_html=True)
