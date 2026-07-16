# Changelog

## [1.8.2] — 2026-07-16

### Nouveautés
- **Revente d'objets** dans l'inventaire de l'Atelier : bouton « Vendre » sur chaque composant,
  avec popup de confirmation. Rembourse **50% du coût de base** (plancher 1 crédit), quel que
  soit le niveau d'amélioration
- Nouvelle route `POST /forge/vendre/<id>` — protection IDOR (`DELETE ... WHERE joueur_id
  RETURNING`), remboursement recalculé côté serveur et crédité dans la même transaction ;
  vendre libère l'emplacement même si l'objet était équipé
- Helper `prix_revente(cout_base)` (source unique vue + route)
- 2 nouveaux tests (`tests/test_web_routes.py`) — total 166 tests

## [1.8.1] — 2026-07-16

### Nouveautés
- **Bouton « Déséquiper »** dans l'inventaire de l'Atelier : permet de retirer un composant
  équipé (arme/sécurité/module), remettant l'emplacement à vide sans coût
- Nouvelle route `POST /forge/desequiper/<id>` — protection IDOR (`WHERE joueur_id` +
  `RETURNING id`), rollback si l'objet est introuvable ou déjà déséquipé
- 2 nouveaux tests (`tests/test_web_routes.py`) — total 163 tests

## [1.8.0] — 2026-07-16

### Refonte thématique : médiéval → informatique
Bascule complète de l'univers dark-fantasy médiéval vers un thème **composants informatiques**
(le technicien devient un **Opérateur**, son personnage un **poste de travail**). Les identifiants
internes (routes, codes badges, `materiau_code`, colonnes SQL, `passif_code`) restent **inchangés** :
seul l'affichage change. Migration rétroactive incluse.

- **Modules renommés** : Aventurier→**Poste**, Forge→**Atelier**, Arène→**Benchmark**,
  Expédition→**Scan réseau**, Journal→**Logs**, Badges→**Certifications** (Classement conservé)
- **Stats** : Force→**CPU**, Constitution→**RAM**, Agilité→**Débit**, Esprit→**Firewall**
- **Monnaie** : Or→**Crédits** (colonne `or_monnaie` inchangée)
- **15 objets Forge** re-thématisés : armes→processeurs (Pentium I → CPU Quantique),
  armures→sécurité (Pare-feu basique → Zero Trust), amulettes→modules (Barrette RAM → Cœur IA)
- **5 matériaux** : Or→Crédits, Bois de Chêne→**Câble réseau**, Minerai de Fer→**Silicium**,
  Cristal Runique→**Circuit imprimé**, Essence du Néant→**Qubit**
- **31 certifications** (ex-badges) renommées : Chevalier→Technicien, Paladin→Ingénieur Système,
  Forgeron→Assembleur, Gladiateur→Challenger, etc.

### Visuel
- Palette dark-fantasy or/brun/parchemin → thème **« terminal » slate/cyan** (variables CSS
  conservées, valeurs remplacées ; glows dorés → cyan)
- Polices Cinzel/Crimson → **piles monospace/système** (plus d'`@import` externe : la CSP
  `font-src 'self'` bloquait déjà les CDN, fallback système instantané et sans appel tiers)
- **Favicon** épée dorée → **puce/CPU** cyan

### Base de données (migration rétroactive, non cassante)
- `_seed_badges` passe en **UPSERT** (`ON CONFLICT DO UPDATE`) : les certifications déjà
  débloquées prennent les nouveaux noms/icônes au démarrage (codes/FK intacts)
- **Migration #9** : `UPDATE equipements` renomme les composants déjà possédés (apostrophes
  SQL échappées, idempotente)

### Tests
- 4 tests d'assertions de chaînes mis à jour (`tests/test_web_routes.py`) — total **160 tests** au vert

## [1.7.1] — 2026-06-22

### Nouveautés
- **Favicon** : icône d'onglet SVG (épée dorée sur fond brun, palette du thème), liée dans `base.html` et `login.html`

## [1.7.0] — 2026-06-22

### Nouveautés
- **Infos contextuelles dans la sidebar** (visibles sur toutes les pages, joueur connecté) :
  - **Version applicative** sous le bouton Déconnexion — lue depuis le nouveau fichier `VERSION` à la racine (source unique de version), exposée aussi sur la page de login (remplace le `v1.4.0` figé)
  - **Saison courante + compte à rebours** avant le reset mensuel (1er du mois à 00:00 UTC) — affiche « moins d'1h restant » dans la dernière heure
  - **XP restant** avant le prochain niveau, sous le niveau courant
  - **Badge rouge** des points de statistique non attribués, sur le niveau
- Nouveau fichier `VERSION` + `_lire_version()` : centralise le numéro de version (fallback `?` si absent)
- `Dockerfile` : copie du fichier `VERSION` dans l'image
- **36 nouveaux tests** (`tests/test_sidebar.py`) — total 160 tests

### Corrections / robustesse
- Context processor `inject_sidebar` : fallback `_SIDEBAR_VIDE` complet (toutes les clés définies) + logging des exceptions DB avalées (`get_joueur`, `get_saison_courante`)

## [1.6.0] — 2026-06-21

### Nouveautés
- **Système de saisons** : reset mensuel automatique le 1er de chaque mois à minuit UTC
  - Tables `saisons` + `saison_archives` (migrations 6 + timestamp `cree_a` sur combats #7 + index unicité partielle #8)
  - `archiver_et_reset_saison()` : transaction unique (archivage + badges + reset joueurs + suppression équipements/matériaux)
  - Worker : Pass 4 `_verifier_reset_saison()` — horloge DB, garde idempotente, `FOR UPDATE` + rowcount guard anti-double-reset
  - Reset scope : XP→0, level→1, stats→10, or→50, PC→1000, pity→0, équipements supprimés, matériaux supprimés
  - Conservé : badges, `tickets_traites`, historique combats
- **3 nouveaux badges saison** : Champion de Saison (👑 XP), Gladiateur de Saison (🏆 PC), Héros de Saison (🎖️ top 3)
- **Affichage numéro de saison** sur la page Classement
- **14 nouveaux tests** (`tests/test_saison.py`) — total 124 tests

### Sécurité
- Reset atomique : `FOR UPDATE` sur la saison + `UPDATE ... WHERE statut='en_cours' AND rowcount==1` + index unique partiel
- `init_saison_si_absente` : INSERT atomique `WHERE NOT EXISTS` (élimine la race condition)
- `conn.rollback()` explicite dans le `except` du worker + `try/finally` pour garantir `conn.close()`
- Logging des exceptions `get_saison_courante()` dans la route classement

## [1.4.1] — 2026-06-21

### Sécurité
- Protection CSRF via Flask-WTF : token dans tous les formulaires HTML + header `X-CSRFToken` injecté globalement sur tous les `hx-post` HTMX
- Correction IDOR `/arene/combat-partial` : vérification ownership avant d'afficher le fragment de combat
- Correction précédence Jinja2 : `{{ (t.analyse_llm or '') | e }}` dans journal.html et aventurier.html

### Qualité
- Refactoring arene.py : constante `HTMX_STOP_POLLING`, helpers `_render_fin_message`/`_render_attente_fin`, renommages explicites
- Refactoring forge.py : constantes `COUT_UPGRADE_RATIO`, `REMISE_BOIS`, `AMELIORATION_MAX` + `cout_amelioration()`
- Refactoring expedition.py : `secondes_restantes` en variable unique, noms `heures/minutes/secondes`
- 41 nouveaux tests Flask (`tests/test_web_routes.py`) — total 107 tests
- Docstrings `web/auth.py` et `web/queries.py`, README mis à jour (stack Flask, env, architecture)

## [1.4.0] — 2026-06-21

### Nouveautés
- **Réécriture complète du frontend** : remplacement de Streamlit par Flask 3 + Jinja2 + HTMX
  - Architecture page-par-page stricte : chaque route est isolée dans son propre Blueprint
  - Zéro contamination inter-pages par construction (pas de session Streamlit partagée, pas de fragments `run_every`)
  - HTMX polling `outerHTML` (2s combat, 3s attente, 30s expédition) — le polling s'arrête proprement quand le div porteur est remplacé (+ code 286)
  - Authentification via cookies de session HTTP signés (`flask.session`) — suppression du mécanisme token-dans-URL
  - Backend (`sync/`) inchangé : seul le frontend change de stack

### Infrastructure
- `Dockerfile` : remplace `COPY app/` par `COPY web/`, supprime le patch Streamlit
- `docker-compose.yml` : `app` passe de `streamlit run` à `gunicorn --workers 4`
- `requirements.txt` : `flask>=3.0` + `gunicorn>=21.0` remplacent `streamlit` + `pandas`
- `.env` : ajout `SECRET_KEY` pour la signature des cookies Flask

### Correctifs intégrés
- Forge : vérification serveur des matériaux ET commit atomique unique (or + équipement + matériaux)
- Arène : garde `combat_id is None` sur toutes les routes HTMX, erreur `jouer_action` remontée en flash
- Expédition : exception badge post-commit catchée pour garantir l'affichage du butin

## [1.3.2] — 2026-06-20

### Correctifs
- **Contamination inter-pages** : suppression du `st.rerun(scope="app")` auto-déclenché depuis le fragment `run_every=1` de l'Arena — cause principale du rendu d'éléments étrangers sur les autres pages. Fin de combat désormais signalée par un bouton utilisateur explicite.
- **Arena** : `run_every` passé de 1s/2s à 3s sur les deux fragments (combat actif, défi en attente), suppression de l'appel `init_db()` (ne doit être que dans le worker).
- **Fuite de connexions** : remplacement des `conn.close()` manuels dans les fragments par `try/finally` — garantit la libération de la connexion même en cas d'exception.
- **Erreur BDD migration** : `tous_les_joueurs()` wrappé dans `try/except` dans Classement, Arena et auth — affiche un message clair si la colonne `points_combat` n'est pas encore migrée (worker à rebuilder).
- **Division par zéro** (latente) : protection de `pv_att / att_pv_max` dans le fragment combat via `max(1, ...)`.

### Qualité
- `auth.login_glpi()` décomposé en trois fonctions privées testables : `_request_access_token`, `_glpi_id_from_token`, `_glpi_id_from_username`.
- Helper `afficher_fin_et_bouton_lobby()` extrait pour dédupliquer la logique de fin de combat/défi.
- 20 nouveaux tests unitaires (auth helpers) — suite totale : 66 tests.

## [1.3.1] — 2026-06-19

### Correctifs
- Fix KeyError `points_combat` dans les tests (`make_joueur()` manquait la clé)

## [1.3.0] — 2026-06-19

### Nouveautés
- Points de Combat (PC) / système Elo (K=32) dans l'Arène
- Colonne PC dans le classement + mise en évidence du joueur connecté (#VOUS)
- Nombre de victoires dans le classement
- 8 nouveaux tests Elo

## [1.2.3] — 2026-06-18

### Correctifs
- XSS dans le classement (`html.escape` sur les usernames)
- Import `xp_requis_pour_niveau` déplacé hors de la boucle

## [1.2.2] — 2026-06-18

### Correctifs
- Réclamation expédition atomique (commit unique)
- Protection double-réclamation (`AND reclamee = FALSE` + rowcount)

## [1.2.1] — 2026-06-18

### Correctifs
- `st.balloons()` toujours affiché (pas seulement si nouveaux badges)
- `perfection_absolue` : `COUNT(DISTINCT type)` au lieu de `COUNT(*)`
- Badges arena affichés (résultat de `jouer_action` capturé)

## [1.2.0] — 2026-06-18

### Nouveautés
- 12 nouveaux badges (expédition, forge, combat, tickets)
- Badge `set_legendaire` et `perfection_absolue` (forge T5 complet)
- Points de combat initialisés à 1000 (migration #5)

## [1.0.7] — 2026-06-17

### Correctifs
- Fix or expédition + prix forge T3-T5

## [1.0.6] — 2026-06-17

### Correctifs
- Suppression du double worker

## [1.0.5] — 2026-06-17

### Correctifs
- Durcissement sécurité Moyens

## [1.0.4] — 2026-06-17

### Correctifs
- Fix 3 findings sécurité Élèves

## [1.0.3] — 2026-06-17

### Correctifs
- Spinner login custom animé
