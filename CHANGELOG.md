# Changelog

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
