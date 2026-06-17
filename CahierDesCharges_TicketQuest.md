# 📑 Cahier des Charges Fonctionnel & Technique

## Projet : TicketQuest (Gamification de GLPI)

**Version :** 1.0 — Document de référence
**Statut :** Validé pour démarrage du développement, hors annexes listées en section 7.

---

## 1. Objectif du Projet

L'objectif de **TicketQuest** est de transformer l'activité quotidienne de support technique (la gestion des tickets dans GLPI) en un jeu de rôle (RPG) médiéval et addictif.

Le projet vise trois buts principaux :

* **Engager les techniciens** en récompensant directement leur productivité.
* **Garantir la qualité des données** saisies dans le SI en valorisant le respect strict des procédures internes de l'entreprise.
* **Maintenir une infrastructure souveraine** et gratuite à l'aide d'outils open-source auto-hébergés en environnement HomeLab.

---

## 2. Périmètre Fonctionnel (Le Gameplay)

### A. L'Aventurier (Le Technicien)

Chaque technicien possède un unique avatar (un Aventurier) lié directement à son identité GLPI (même ID/nom d'utilisateur). La progression de cet avatar est strictement linéaire et repose sur quatre statistiques principales :

* **Force / Puissance :** Augmente les dégâts physiques ou magiques infligés lors des combats.
* **Constitution / PV :** Détermine la réserve totale de points de vie de l'aventurier.
* **Agilité / Vitesse :** Détermine l'ordre de passage (l'initiative) lors des combats et la probabilité d'esquiver une attaque.
* **Esprit / Résistance :** Réduit passivement les dégâts subis par les attaques adverses.

À chaque **montée de niveau** déclenchée par l'accumulation d'XP, le joueur reçoit des points de statistiques qu'il peut répartir librement sur son interface web pour orienter son style de jeu.

### B. Le Moteur d'XP et de Gains (L'interfaçage GLPI)

Les points d'expérience (XP) et les récompenses ne sont attribués **qu'au moment de la clôture/résolution d'un ticket** dans GLPI. Le calcul s'appuie sur quatre critères :

1. **L'Urgence & l'Impact :** Multiplicateur basé sur la matrice de priorité native de GLPI.
2. **La Catégorie du ticket :** Grille de points fixe définie à l'avance (ex : *Incident Réseau Majeur = 100 XP*, *Demande d'attribution de souris = 10 XP*). La grille exhaustive par catégorie GLPI fait l'objet de l'**Annexe A** (voir section 7).
3. **L'Analyse Sémantique :** Une évaluation du titre et de la description pour affiner la complexité réelle du problème.
4. **Le Bonus de Conformité (La Qualité) :** Déterminant pour l'économie du jeu. Le texte de résolution est passé au crible par l'IA locale (Ollama). S'il est validé, le joueur reçoit un **bonus d'XP massif (+50%)** et de l'or.

Aucun système de malus / pénalité (réouverture de ticket, dépassement de SLA, etc.) n'est prévu dans cette première version du jeu.

### C. Économie : Expéditions (Offtime) et Forge

L'or accumulé grâce aux tickets conformes ouvre l'accès aux boucles de gameplay secondaires sur l'application Web :

* **Les Expéditions :** Le joueur peut envoyer son personnage en mission passive (qui s'exécute en tâche de fond). Plus le niveau de l'aventurier est élevé, plus il a accès à des expéditions "riches" (récompenses plus importantes).
* **Le Butin (Loot) :** Les expéditions rapportent de l'or, mais aussi des **matériaux de fabrication** et des pièces d'équipement de base (Armes, Armures, Amulettes), de façon aléatoire (mécanique de type Hack'n'Slash / Diablo).
* **La Forge :** Permet de combiner les matériaux collectés pour fabriquer des **armes uniques**, augmentant de manière fixe et linéaire les statistiques du personnage (ex : *Épée en fer = +5 Force*).

> Ce modèle hybride combine les deux options évoquées en discussion : le **loot aléatoire** intervient au niveau des expéditions (découverte d'équipements de base et de matériaux), tandis que la **forge** applique des bonus fixes et prévisibles lors de la fabrication d'objets améliorés.

### D. Le Système de Duel (Joueur contre Joueur)

Le jeu propose une arène en ligne où les techniciens peuvent s'affronter lors de **combats actifs au tour par tour** :

1. **Le Défi :** Un technicien provoque un collègue disponible via l'interface web.
2. **L'Arène :** Une fois le défi accepté, le combat s'ouvre. Le jeu calcule l'initiative selon l'Agilité de chacun pour désigner le premier joueur à attaquer.
3. **Les Actions :** À chaque tour, le joueur choisit activement son action parmi 3 ou 4 compétences (ex : *Attaque Lourde, Posture Défensive, Contre-attaque*), liées à son équipement.
4. **Résolution :** Les dégâts sont calculés selon la formule théorique :

$$\text{Dégâts} = (\text{Force de l'attaquant} \times \text{Multiplicateur de compétence}) - \text{Résistance du défenseur}$$

5. Le premier joueur dont les PV tombent à 0 perd le combat. Le vainqueur remporte une distinction honorifique (titre) ou une somme d'or symbolique.

---

## 3. Architecture Technique & Flux de Données

L'application est découpée en quatre composants majeurs, entièrement intégrés au HomeLab.

```
+------------------+          +------------------------+          +-----------------------+
|    GLPI v11      |          |   Synchroniseur (Py)   |          |      Ollama LLM       |
|                  |          |                        |          |                       |
|  [Ticket Clos] ---------->  |  - Requête API GLPI    | -------> |  - Envoi Résolution   |
+------------------+          |  - Analyse du Ticket   | <------- |  - Verdict JSON       |
                              |  - Calcul XP / Or      |          +-----------------------+
                              +-----------+------------+
                                          |
                                          v
                              +-----------+------------+          +-----------------------+
                              |   Base de Données      |          |    Interface Web      |
                              |   (PostgreSQL)         | <------> |     (Streamlit)       |
                              +------------------------+          +-----------------------+
```

### A. Le Synchroniseur (Worker Python)

Un script Python tourne en tâche de fond et interroge l'API REST de GLPI de manière cyclique **toutes les 60 secondes**.

* Il récupère les **Nouveaux tickets** (Statut 1) pour l'historique ou de futures alertes de quêtes.
* Il intercepte les **Tickets Clos** (Statut 5) modifiés depuis son dernier passage pour initier le calcul des récompenses.
* Il intègre un système d'ancrage temporel pour éviter de traiter deux fois le même ticket.

### B. L'Analyse de Conformité par IA Locale (Ollama)

Pour valider le respect des procédures de manière intelligente sans utiliser d'API tierce payante, le système s'appuie sur **Ollama** installé en local avec un modèle léger (ex : *Mistral* ou *Llama3*).

* Le script extrait la solution rédigée par le technicien.
* Il envoie une requête HTTP à l'API d'Ollama (`http://localhost:11434/api/generate`) avec un prompt système strict.
* Le modèle doit analyser la présence des critères obligatoires (ex : *Nom, Prénom, Numéro de l'appelant, actions effectuées*) et répondre **obligatoirement sous la forme d'un objet JSON structuré** :

```json
{
  "conforme": true,
  "explication": "Le technicien a correctement documenté l'identité de l'appelant ainsi que la procédure de réinitialisation appliquée."
}
```

> La liste exhaustive des critères obligatoires (issue de la procédure interne) fait l'objet de l'**Annexe B** (voir section 7).

### C. Le Backend & Base de Données du Jeu

* **Framework :** Python (FastAPI). Gère l'API du jeu, la logique des expéditions de fond, et fait office de "Machine à états" (State Machine) pour orchestrer les combats au tour par tour sans désynchronisation entre les deux joueurs.
* **Base de données :** PostgreSQL.

### D. Le Frontend (L'Interface Joueur)

Une application web dédiée développée avec **Streamlit**, accessible sur un écran secondaire à côté de GLPI. Elle affiche :

* Le tableau de bord de l'aventurier (Niveau, XP, Statistiques, Équipement actuel).
* Le menu de la Forge et la gestion des Expéditions en cours.
* L'arène de combat Joueur contre Joueur (PvP) en temps réel.

---

## 4. Plan de Charge et Étapes de Déploiement Suggérées

Pour mener à bien le développement dans le Homelab, le projet suivra l'ordre d'implémentation suivant :

1. **Brique 1 : Connectivité API** — Établir les sessions GLPI et valider la capture brute des flux de tickets toutes les 60 secondes.
2. **Brique 2 : IA & Conformité** — Mise en place du conteneur/service Ollama, rédaction de la liste des critères de conformité (Annexe B), création du prompt de test et parsing du retour JSON.
3. **Brique 3 : Base de Données & Logique RPG** — Création des tables joueurs/équipements (PostgreSQL), finalisation de la grille de points par catégorie (Annexe A), gestion de l'attribution de l'XP et mécanique des niveaux.
4. **Brique 4 : Interface Web & Forge** — Création des pages profils (Streamlit), système d'exploration passive et d'artisanat.
5. **Brique 5 : Système de Combat** — Code de la boucle de combat actif au tour par tour en PvP.

---

## 5. Spécifications Techniques Détaillées des Briques

### A. La Base de Données (Schéma Relationnel - PostgreSQL)

Pour soutenir ce gameplay centré sur l'évolution linéaire du personnage, voici l'architecture exacte des tables à implémenter :

```
+-------------------------------------------------------+
|                       JOUEURS                         |
+-------------------------------------------------------+
| id (PK)           : INT (ID Utilisateur GLPI)         |
| username          : VARCHAR                           |
| level             : INT (Défaut: 1)                   |
| xp                : INT (Défaut: 0)                   |
| or                : INT (Défaut: 0)                   |
| force_p           : INT (Défaut: 10)                  |
| constitution_pv   : INT (Défaut: 10)                  |
| agilite_vit       : INT (Défaut: 10)                  |
| esprit_res        : INT (Défaut: 10)                  |
| points_a_attribuer: INT (Défaut: 0)                   |
+-------------------------------------------------------+
                           | 1
                           |
                           | 0..*
+-------------------------------------------------------+
|                     EQUIPEMENTS                       |
+-------------------------------------------------------+
| id (PK)           : INT                               |
| joueur_id (FK)    : INT                               |
| nom               : VARCHAR                           |
| type              : VARCHAR ('arme', 'armure', 'amul')|
| bonus_stat        : VARCHAR ('force', 'pv', 'vit'...) |
| valeur_bonus      : INT                               |
| equipe            : BOOLEAN (Défaut: false)           |
+-------------------------------------------------------+
```

En complément des tables ci-dessus, les tables suivantes sont nécessaires au fonctionnement global :

```
+-------------------------------------------------------+
|                  TICKETS_TRAITES                       |
+-------------------------------------------------------+
| ticket_id (PK)    : INT (ID Ticket GLPI)               |
| joueur_id (FK)    : INT                                |
| xp_gagne          : INT                                |
| conforme          : BOOLEAN (Verdict LLM Ollama)       |
| analyse_llm       : TEXT (Explication renvoyée par IA) |
| date_traitement   : DATETIME                           |
+-------------------------------------------------------+

+-------------------------------------------------------+
|                       COMBATS                          |
+-------------------------------------------------------+
| id (PK)           : INT                                |
| attaquant_id (FK) : INT (Joueur 1)                     |
| defenseur_id (FK) : INT (Joueur 2)                     |
| statut            : VARCHAR ('en_attente','en_cours','termine') |
| tour_de_qui       : INT (ID du joueur devant jouer)    |
| log_combat        : TEXT (Résumé des actions)          |
+-------------------------------------------------------+
```

### B. Algorithme du Calcul d'XP (Le Moteur)

Lorsqu'un ticket est capturé avec le statut "Clos", l'application applique la formule suivante pour déterminer le gain :

$$\text{XP Gagnée} = (\text{Points Catégorie} \times \text{Multiplicateur Priorité}) \times \text{Bonus Conformité IA}$$

* **Grille Priorité GLPI :** Très basse ($\times 0.5$), Moyenne ($\times 1.0$), Très haute ($\times 2.0$).
* **Bonus Conformité IA :** Si le JSON d'Ollama renvoie `"conforme": true`, le coefficient est de $1.5$ (soit +50% d'XP), sinon il reste à $1.0$.

### C. Logique de l'Arène PvP (La State Machine)

Pour que le combat actif au tour par tour fonctionne sans accroc en HTTP (FastAPI), le backend gère un dictionnaire d'états pour chaque combat actif :

* `ETAT_ATTENTE` : Le Joueur 1 attend que le Joueur 2 accepte le défi.
* `ETAT_TOUR_J1` : L'interface du Joueur 1 débloque les boutons d'action. L'interface du Joueur 2 affiche "Votre adversaire réfléchit...".
* `ETAT_LOGIQUE` : Le backend reçoit l'action, calcule les dégâts, soustrait les PV, écrit la ligne dans le journal de combat, puis passe le statut à `ETAT_TOUR_J2`.
* `ETAT_FIN` : Un des compteurs de PV est tombé à zéro. Les gains sont distribués, le combat est archivé.

---

## 6. Contraintes & Critères de Succès

### Contraintes Techniques

* **Sécurité des Jetons :** L'App-Token et le User-Token de GLPI ne doivent jamais apparaître en clair dans le code source (utilisation d'un fichier `.env` ou de variables d'environnement).
* **Idempotence :** Le script de synchronisation ne doit **sous aucun prétexte** attribuer deux fois des points pour un même ID de ticket. Chaque transaction réussie doit immédiatement inscrire l'ID du ticket dans la table `tickets_traites`.
* **Ressources du Homelab :** L'appel à Ollama devant se faire toutes les 60 secondes, le modèle choisi (ex : *Llama3-8B* ou *Mistral-7B*) doit être configuré pour s'exécuter rapidement afin de ne pas bloquer la boucle du script Python.

### Critères de Validation du Projet (DOD - Definition of Done)

1. Un technicien ferme un ticket conforme aux procédures dans GLPI → Moins de 60 secondes après, son personnage gagne de l'XP et de l'or sur l'interface web, et le log de l'IA est consultable.
2. Un personnage accumule assez d'XP → Il passe au niveau supérieur et peut cliquer sur des boutons pour ajouter manuellement des points à sa Force ou sa Vitesse.
3. Deux techniciens ouvrent l'arène → Ils peuvent s'infliger des dégâts mutuellement jusqu'à ce que mort s'ensuive (virtuellement, bien sûr), en respectant strictement l'ordre d'agilité de leurs fiches de personnage.

---

## 7. Annexes à Compléter (Livrables en cours)

Les éléments suivants sont identifiés comme nécessaires au projet, mais leur contenu détaillé reste à produire au cours des briques concernées. Le développement des composants génériques peut démarrer en parallèle sur la base de jeux de données d'exemple.

### Annexe A — Grille de points par catégorie de ticket (Brique 3)

* Liste exhaustive des catégories GLPI utilisées par l'organisation, avec le nombre de points XP de base associé à chacune.
* Exemples de référence déjà actés : *Incident Réseau Majeur = 100 XP*, *Demande d'attribution de souris = 10 XP*.
* À produire avant le démarrage de la Brique 3 (Base de Données & Logique RPG).

### Annexe B — Critères de conformité pour l'analyse IA (Brique 2)

* Liste des informations et éléments de mise en page obligatoires dans un ticket selon la procédure interne (ex : lors d'un appel — Nom + Prénom + Numéro de l'appelant + Sujet du problème).
* Cette liste servira de base au prompt envoyé à Ollama et à la grille de vérification de conformité.
* À rédiger pendant la Brique 2 (IA & Conformité), en s'appuyant sur des exemples génériques pour démarrer le développement.

---

*Document consolidé à partir des échanges de spécification du projet TicketQuest.*
