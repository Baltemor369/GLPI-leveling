# GlpiLeveling

Transformez la gestion de tickets GLPI en jeu de rôle médiéval pour vos techniciens.  
Chaque ticket résolu rapporte de l'XP, fait monter de niveau et débloque équipements, badges et combats PvP.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation rapide (Docker)](#installation-rapide-docker)
- [Configuration GLPI](#configuration-glpi)
- [Développement local](#développement-local)
- [Mécanique de jeu](#mécanique-de-jeu)

---

## Fonctionnalités

| Module | Description |
|---|---|
| **Aventurier** | Profil RPG par technicien — XP, niveau, stats (Force / Constitution / Agilité / Esprit) |
| **Forge** | 15 équipements en 5 tiers (armes, armures, amulettes) avec passifs et améliorations +1→+20 |
| **Arène** | Combats PvP au tour par tour avec esquive, passifs et système de mise en or |
| **Expédition** | Mission de 2h avec loot pondéré (3 rolls par expédition, pity garanti à 10 expéditions) |
| **Badges** | 20 succès débloquables (tickets, combats, forge, niveaux) |
| **Classement** | Tableau des techniciens par XP / niveau |
| **Worker** | Synchronisation automatique avec GLPI — attribue XP et badges à chaque ticket fermé |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Compose                 │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   app    │  │  worker  │  │  ollama  │  │
│  │Streamlit │  │sync GLPI │  │   LLM    │  │
│  │ :8501    │  │(boucle)  │  │ :11434   │  │
│  └────┬─────┘  └────┬─────┘  └──────────┘  │
│       └─────────────┴──────────┐            │
│                          ┌─────┴──────┐     │
│                          │ PostgreSQL │     │
│                          │    db      │     │
│                          └────────────┘     │
└─────────────────────────────────────────────┘
                     │
              ┌──────┴──────┐
              │ GLPI (ext.) │   votre instance existante
              └─────────────┘
```

- **app** — interface web Streamlit, accessible sur le réseau interne
- **worker** — interroge GLPI toutes les N secondes, traite les tickets fermés via LLM, attribue l'XP
- **ollama** — modèle LLM local (mistral) pour scorer la difficulté et la conformité des tickets
- **db** — PostgreSQL, stocke joueurs, équipements, combats, expéditions, badges
- **GLPI** — votre instance existante, non modifiée

---

## Prérequis

- **Docker** >= 24 et **Docker Compose** >= 2.20
- Accès réseau à votre instance GLPI (API REST activée)
- ~4 Go de RAM disponibles sur le serveur (principalement pour Ollama + mistral)
- ~5 Go d'espace disque (image Ollama + modèle mistral ~4 Go)

---

## Installation rapide (Docker)

### 1. Cloner le dépôt

```bash
git clone https://github.com/Baltemor369/GLPI-leveling.git
cd GLPI-leveling
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
nano .env   # ou vim, notepad, etc.
```

Remplir obligatoirement :

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL (choisir un mot de passe fort) |
| `DATABASE_URL` | Remplacer `changez_moi` par le même mot de passe que ci-dessus |
| `GLPI_API_BASE_URL` | URL de l'API GLPI, ex: `https://glpi.entreprise.com/api.php` |
| `GLPI_OAUTH_CLIENT_ID` | Client OAuth2 créé dans GLPI (voir section suivante) |
| `GLPI_OAUTH_CLIENT_SECRET` | Secret du client OAuth2 |
| `GLPI_BOT_USERNAME` | Nom du compte bot dans GLPI |
| `GLPI_BOT_PASSWORD` | Mot de passe du compte bot |

### 3. Lancer

```bash
bash start.sh
```

Le script :
1. Démarre la base de données et Ollama
2. Télécharge le modèle mistral (première fois uniquement, ~4 Go)
3. Lance l'application et le worker

L'interface est accessible sur `http://IP_SERVEUR:8501`.

### Commandes utiles

```bash
# Voir les logs en temps réel
docker compose logs -f

# Logs d'un service spécifique
docker compose logs -f worker

# Arrêter
docker compose down

# Arrêter et supprimer les données
docker compose down -v
```

---

## Configuration GLPI

### Créer un client OAuth2

1. Dans GLPI : **Configuration → OAuth 2.0 → Ajouter un client**
2. Nom : `GlpiLeveling`
3. Cocher le grant type `Resource Owner Password`
4. Copier le `client_id` et `client_secret` générés dans votre `.env`

### Créer un compte bot

1. **Administration → Utilisateurs → Ajouter**
2. Nom : `bot-glpileveling` (ou au choix)
3. Droits minimum requis : lecture sur les tickets, lecture sur les utilisateurs
4. Renseigner `GLPI_BOT_USERNAME` et `GLPI_BOT_PASSWORD` dans votre `.env`

### Se connecter à l'application

Les techniciens se connectent avec leurs identifiants GLPI habituels — aucun compte séparé à créer.

---

## Développement local

Sans Docker, pour développer sur Windows :

```powershell
# Installer les dépendances
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Lancer l'app
streamlit run app/Aventurier.py --server.port 8501

# Lancer le worker (dans un autre terminal)
cd sync
python worker.py
```

Prérequis supplémentaires : PostgreSQL local et Ollama installé séparément.

Pour relancer rapidement après un crash :

```powershell
.\restart_app.ps1
```

---

## Mécanique de jeu

### XP par ticket

```
XP = base_catégorie × coeff_urgence × coeff_impact × coeff_difficulté × coeff_rapidité
```

| Paramètre | Valeur |
|---|---|
| Base Serveur | 5 XP |
| Base Poste client | 3 XP |
| Base WiFi / Périphérique | 2 XP |
| Urgence haute (≥ 4) | × 1.2 |
| Impact haut (≥ 4) | × 1.2 |
| Difficulté LLM (1–10) | × (1 + score/10) |
| Rapidité J0 | × 1.5 |
| Rapidité J5+ | × 1.0 (plancher) |

Le technicien créateur du ticket reçoit aussi un **XP de conformité** selon la qualité de saisie évaluée par le LLM (titre, description, coordonnées).

### Montée de niveau

Chaque niveau rapporte **3 points de stats** à distribuer librement entre Force, Constitution, Agilité et Esprit.

### Forge

- 15 équipements en 5 tiers (Fer → Acier → Mithril → Runique → Néant)
- Tiers 3–5 nécessitent des matériaux obtenus en expédition
- Améliorations +1 à +20 : coût = `prix_tier × niveau × 0.6`

### Expédition (2h)

- 3 rolls pondérés par expédition (Or 38%, Bois 28%, Minerai 20%, Cristal 10%, Essence 4%)
- Pity : garantit une Essence du Néant après 10 expéditions sans en obtenir

### Arène PvP

- Combats au tour par tour avec mise d'or optionnelle
- Esquive basée sur l'Agilité du défenseur et la Force de l'attaquant
- 3 types d'attaque avec malus de vitesse (Rapide 0%, Lourde -20%, Critique -40%)
