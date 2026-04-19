# IAM Local — Module 02

> **Système de Gestion des Identités et des Accès (IAM) Local**  
> Composant du système national d'éducation EIGEN  
> Version : **1.0.0**

---

## Table des matières

1. [Vision du projet](#1-vision-du-projet)
2. [Architecture globale](#2-architecture-globale)
3. [Modèle de données](#3-modèle-de-données)
4. [Structure du projet](#4-structure-du-projet)
5. [Installation et démarrage](#5-installation-et-démarrage)
6. [Configuration](#6-configuration)
7. [Bootstrap — Premier démarrage](#7-bootstrap--premier-démarrage)
8. [Migrations de base de données](#8-migrations-de-base-de-données)
9. [Authentification — Guide complet](#9-authentification--guide-complet)
10. [Système de permissions](#10-système-de-permissions)
11. [API — Résumé des routes](#11-api--résumé-des-routes)
12. [Intégration avec les autres modules](#12-intégration-avec-les-autres-modules)
13. [Flux métier clés](#13-flux-métier-clés)
14. [Technologies et dépendances](#14-technologies-et-dépendances)
15. [Variables d'environnement](#15-variables-denvironnement)

---

## 1. Vision du projet

### Contexte national

Le système EIGEN est une plateforme nationale de gestion de l'éducation supérieure.  
Il est composé de :

- **IAM Central** — Référentiel national des comptes étudiants. Détient la vérité absolue sur chaque étudiant à l'échelle nationale. Fournit le SSO.
- **IAM Local (ce module)** — Instance par établissement. Gère les identités locales, les inscriptions, les rôles et permissions propres à l'établissement.
- **Modules métier** — Scolarité, Notes, RH, Finances, Bibliothèque... Consomment les tokens et permissions émis par IAM Local.

### Responsabilités de ce module

| Responsabilité | Description |
|----------------|-------------|
| **Identité locale** | Maintient un `CompteLocal` par utilisateur dans l'établissement, synchronisé avec IAM Central |
| **Multi-inscription** | Un étudiant peut avoir plusieurs `ProfilLocal` (plusieurs inscriptions dans différentes filières) |
| **SSO** | Valide les tokens IAM Central et crée des sessions locales |
| **Auth locale** | Authentification par credentials (username/password) pour les comptes sans SSO |
| **RBAC** | Gestion fine des rôles, permissions et groupes par profil |
| **Audit** | Journal immuable de toutes les actions |
| **Gateway** | Routing sécurisé vers les modules métier |

---

## 2. Architecture globale

```
┌─────────────────────────────────────────────────────────────┐
│                    IAM CENTRAL (national)                    │
│  - Référentiel national des étudiants                        │
│  - SSO / JWKS                                                │
│  - user_id_national = UUID unique par étudiant              │
└───────────────────────┬─────────────────────────────────────┘
                        │  SSO Token (JWT)
                        │  Synchronisation des données
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 IAM LOCAL (cet établissement)                │
│                                                              │
│  CompteLocal                                                 │
│  ├── user_id_national (lien IAM Central)                    │
│  ├── Credentials locaux (password_hash)                     │
│  └── ProfilLocal[1..N]                                      │
│       ├── sub JWT = profil.id                               │
│       ├── Sessions Redis                                     │
│       ├── Permissions & Rôles                               │
│       └── contexte_scolaire (filière, composante...)        │
│                                                              │
│  Token JWT → sub = profil.id                                │
│  Session Redis → clé = profil.id                            │
└──────────┬────────────────────────────────────────┬─────────┘
           │  JWT Bearer                             │  Events Kafka
           ▼                                         ▼
┌──────────────────┐  ┌───────────┐  ┌───────────────────────┐
│ Module Scolarité │  │ Module RH │  │ Module Notes / Finances│
│ port 8003        │  │ port 8005 │  │ port 8004 / 8006       │
└──────────────────┘  └───────────┘  └───────────────────────┘
```

### Flux d'authentification SSO

```
Client → POST /tokens/login  (credentials locaux)
      ou POST /tokens/sso    (token IAM Central)
           │
           ▼
       AuthService
           │
           ├── CredentialService.authenticate_credentials()
           │     → vérifie CompteLocal.password_hash
           │     → retourne (CompteLocal, ProfilLocal)
           │
           ├── HabilitationService.get_habilitations(profil.id)
           │     → calcule permissions effectives
           │     → cache Redis 15 min
           │
           └── TokenManager.authenticate_user()
                 → crée session Redis (clé: profil.id)
                 → génère JWT (sub: profil.id)
                 → retourne {access_token, refresh_token}
```

---

## 3. Modèle de données

### Vue d'ensemble

```
CompteLocal                ProfilLocal
┌──────────────────┐      ┌──────────────────────┐
│ id (PK)          │      │ id (PK)               │
│ user_id_national │◄─┐   │ compte_id (FK) ───────┤──►  CompteLocal
│ nom, prenom      │  │   │ username              │
│ email, telephone │  │   │ type_profil           │
│ identifiant_nat. │  │   │ statut                │
│ username         │  │   │ contexte_scolaire     │  AssignationRole
│ statut           │  │   │ derniere_connexion     │  ┌────────────┐
│ password_hash    │  │   │ nb_connexions          ├──┤ profil_id  │
│ password_salt    │  │   │ preferences            │  │ role_id    │
│ snapshot_iam_c.  │  │   │ meta_data, notes       │  └────────────┘
│ preferences      │  └───┤                        │
│ meta_data, notes │      └──────────────────────┬─┘  AssignationGroupe
└──────────────────┘                             │    ┌────────────┐
                                                 └────┤ profil_id  │
                                                      │ groupe_id  │
                                                      └────────────┘

Role                 Groupe              Permission
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ id, code     │    │ id, code     │    │ id, code     │
│ nom          │    │ nom, type    │    │ domaine      │
│ permissions  │    │ roles[]      │    │ ressource    │
│ type         │    │ membres[]    │    │ action       │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Séparation CompteLocal / ProfilLocal

**CompteLocal** → identité, credentials, lien IAM Central  
**ProfilLocal** → inscription, rôles, permissions, JWT sub

| Champ | CompteLocal | ProfilLocal |
|-------|:-----------:|:-----------:|
| `user_id_national` | ✅ | ❌ |
| `nom`, `prenom`, `email` | ✅ | ❌ |
| `identifiant_national` | ✅ | ❌ |
| `password_hash`, `password_salt` | ✅ | ❌ |
| `snapshot_iam_central` | ✅ | ❌ |
| `compte_id` (FK) | ❌ | ✅ |
| `type_profil` | ❌ | ✅ |
| `contexte_scolaire` | ❌ | ✅ |
| `sub JWT` | ❌ | ✅ |
| Rôles / Permissions | ❌ | ✅ |
| Sessions Redis | ❌ | ✅ |

### Types de profil (`type_profil`)

| Valeur | Description |
|--------|-------------|
| `etudiant` | Étudiant inscrit |
| `enseignant` | Enseignant |
| `enseignant_chercheur` | Enseignant-chercheur |
| `personnel_admin` | Personnel administratif |
| `personnel_technique` | Personnel technique |
| `direction` | Direction de l'établissement |
| `invite` | Invité / accès limité |
| `systeme` | Compte système (bootstrap, services) |

### Statuts

| Valeur | CompteLocal | ProfilLocal | Description |
|--------|:-----------:|:-----------:|-------------|
| `actif` | ✅ | ✅ | Normal, opérationnel |
| `inactif` | ✅ | ✅ | Désactivé manuellement |
| `suspendu` | ✅ | ✅ | Suspendu avec motif |
| `expire` | ✅ | ✅ | Accès expiré |
| `bootstrap` | ✅ | ✅ | Temporaire bootstrap (à supprimer) |

---

## 4. Structure du projet

```
EIGEN_National_Backend_IAM_Local_V1/
│
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── comptes.py          # Routes CompteLocal (NOUVEAU)
│   │       ├── profils.py          # Routes ProfilLocal
│   │       ├── roles.py            # Routes Rôles
│   │       ├── groupes.py          # Routes Groupes
│   │       ├── permissions.py      # Routes Permissions
│   │       ├── habilitations.py    # Routes Habilitations
│   │       ├── audit.py            # Routes Audit
│   │       ├── token_endpoints.py  # Routes Auth/Tokens
│   │       ├── token_config.py     # Routes Config Tokens
│   │       ├── gateway.py          # Routes Gateway
│   │       ├── admin.py            # Routes Admin
│   │       ├── endpoints.py        # Routes Enregistrement Endpoints
│   │       └── router.py           # Assemblage des routes
│   │
│   ├── models/
│   │   ├── compte_local.py         # NOUVEAU — identité + credentials
│   │   ├── profil_local.py         # REFACTORISÉ — inscription + droits
│   │   ├── role.py
│   │   ├── groupe.py
│   │   ├── permission.py
│   │   ├── assignation_role.py
│   │   ├── assignation_groupe.py
│   │   ├── delegation.py
│   │   ├── journal_acces.py
│   │   ├── token_models.py
│   │   └── base.py                 # BaseModel (UUID PK, timestamps, soft delete)
│   │
│   ├── repositories/
│   │   ├── compte_local.py         # NOUVEAU
│   │   ├── profil_local.py         # REFACTORISÉ (jointures CompteLocal)
│   │   ├── base.py                 # BaseRepository générique
│   │   └── ...
│   │
│   ├── schemas/
│   │   ├── compte_local.py         # NOUVEAU — Pydantic CompteLocal
│   │   ├── profil_local.py         # REFACTORISÉ — champs compte dénormalisés
│   │   ├── habilitation.py
│   │   ├── assignation.py
│   │   └── ...
│   │
│   ├── services/
│   │   ├── compte_local_service.py # NOUVEAU — CRUD CompteLocal + sync SSO
│   │   ├── profil_service.py       # REFACTORISÉ — CRUD ProfilLocal
│   │   ├── auth_service.py         # REFACTORISÉ — auth locale + SSO
│   │   ├── credential_service.py   # REFACTORISÉ — opère sur CompteLocal
│   │   ├── habilitation_service.py # Calcul permissions (cache 15 min)
│   │   ├── audit_service.py        # Journal immuable
│   │   ├── role_service.py
│   │   ├── groupe_service.py
│   │   ├── permission_service.py
│   │   ├── gateway_service.py
│   │   ├── bootstrap_cleanup_service.py
│   │   └── token_manager/          # Gestion JWT + sessions Redis
│   │       ├── token_manager.py    # Orchestrateur principal
│   │       ├── access_token_service.py
│   │       ├── refresh_token_service.py
│   │       ├── session_manager.py
│   │       ├── token_validator.py
│   │       ├── token_blacklist_service.py
│   │       ├── token_config_service.py
│   │       ├── sync_service.py
│   │       └── device_analysis_service.py
│   │
│   ├── core/
│   │   ├── exceptions.py           # Exceptions métier
│   │   ├── enums.py                # TypeProfil, StatutProfil, etc.
│   │   └── bootstrap_config.py     # Constantes bootstrap
│   │
│   ├── middleware/
│   │   └── auth.py                 # get_current_user, require_permission()
│   │
│   ├── infrastructure/
│   │   ├── cache/redis.py          # CacheService (Redis)
│   │   └── kafka/                  # Producteur/Consommateur Kafka
│   │
│   ├── config.py                   # Settings (pydantic-settings)
│   ├── database.py                 # AsyncSession SQLAlchemy
│   └── main.py                     # FastAPI app factory
│
├── migrations/
│   ├── env.py                      # Alembic env
│   └── versions/                   # Fichiers de migration (à régénérer)
│
├── seeds/
│   ├── bootstrap.py                # Service bootstrap
│   ├── data/
│   │   ├── permissions.yaml        # Permissions initiales
│   │   ├── roles.yaml              # Rôles initiaux
│   │   └── groupes.yaml            # Groupes initiaux
│   └── scripts/
│       └── run_bootstrap.py        # Script de lancement
│
├── docs/
│   ├── API_REFERENCE.md            # Documentation complète des routes
│   ├── API_COMPLETE_IAM.md         # Ancienne doc (référence)
│   ├── CURL_COMMANDS_IAM.md        # Exemples cURL
│   └── GATEWAY_ARCHITECTURE.md    # Architecture Gateway
│
├── docker-compose-dev.yml
├── docker-compose-prod.yml
├── Dockerfile
├── alembic.ini
├── pyproject.toml
└── README.md
```

---

## 5. Installation et démarrage

### Prérequis

- Python 3.11+
- PostgreSQL 16+
- Redis 7+
- Kafka (optionnel en dev)
- Docker / Docker Compose (recommandé)

### Avec Docker (recommandé)

```bash
# 1. Cloner le projet
git clone https://github.com/amourgit/IAM-Local-Backend.git
cd IAM-Local-Backend

# 2. Copier et configurer l'environnement
cp .env.example .env
# Éditer .env avec vos valeurs

# 3. Tout en une commande (docker + install + migrate + bootstrap + run)
make setup-dev
```

### Étape par étape

```bash
# 1. Démarrer PostgreSQL (port 5433), Redis, Kafka
make docker-dev

# 2. Installer les dépendances Python
make install

# 3. Générer et appliquer les migrations depuis les modèles
make migrate-auto    # génère la migration depuis les modèles SQLAlchemy
make migrate         # applique : alembic upgrade head

# 4. Lancer le bootstrap (UNE SEULE FOIS — crée seeds + profil admin temporaire)
make bootstrap

# 5. Démarrer l'API (port 8002, rechargement automatique)
make run
```

### Sans Docker

```bash
# PostgreSQL et Redis doivent être déjà démarrés

make install
make migrate-auto   # génère la migration
make migrate        # applique alembic upgrade head
make bootstrap      # insère seeds + crée profil bootstrap
make run
```

### Vérification

```bash
curl http://localhost:8002/health
# → {"status": "ok", "service": "iam-local"}

# Swagger UI
open http://localhost:8002/docs
```

---

## 6. Configuration

Copier `.env.example` en `.env` :

```bash
cp .env.example .env
```

Toutes les variables sont documentées dans la section [Variables d'environnement](#15-variables-denvironnement).

**Variables obligatoires :**

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/iam_local
JWT_SECRET_KEY=votre-cle-secrete-longue-et-aleatoire
ETABLISSEMENT_ID=uuid-de-votre-etablissement
ETABLISSEMENT_CODE=UOB
```

---

## 7. Bootstrap — Premier démarrage

Le bootstrap crée automatiquement :
1. Un `CompteLocal` temporaire (`statut: bootstrap`)
2. Un `ProfilLocal` associé (`type: systeme`)
3. Le rôle `iam.admin_temp` assigné au profil
4. Un token JWT valide **48 heures**

### Lancer le bootstrap

```bash
python seeds/scripts/run_bootstrap.py
```

Output :

```
============================================================
BOOTSTRAP IAM LOCAL — DÉMARRAGE
============================================================
   → 7 rôles récupérés depuis la DB
   ✅ ProfilLocal bootstrap créé — rôle iam.admin_temp assigné
   ✅ Session bootstrap créée (TTL: 48h)
============================================================
✅ BOOTSTRAP TERMINÉ AVEC SUCCÈS
============================================================
⚠️  TOKEN BOOTSTRAP VALIDE 48H
```

### Utiliser le token bootstrap

Le token est affiché dans la console et sauvegardé dans `bootstrap_credentials.json`.

```bash
# Créer le premier admin réel
curl -X POST http://localhost:8002/api/v1/profils/ \
  -H "Authorization: Bearer <token_bootstrap>" \
  -H "Content-Type: application/json" \
  -d '{
    "nom": "ONDO", "prenom": "Mireille",
    "email": "admin@universite.ga",
    "identifiant_national": "ADM001",
    "username": "mireille.ondo.ADM001",
    "password": "AdminSecure@2024!",
    "type_profil": "direction"
  }'

# Assigner le rôle iam.admin
curl -X POST http://localhost:8002/api/v1/profils/<profil_id>/roles \
  -H "Authorization: Bearer <token_bootstrap>" \
  -d '{"role_id": "<role_iam_admin_id>"}'
```

### Nettoyage automatique

Dès que l'admin réel se connecte pour la première fois, le profil bootstrap est **automatiquement supprimé** et le token bootstrap invalidé dans Redis.

---

## 8. Migrations de base de données

> ⚠️ **Toutes les anciennes migrations ont été supprimées.** Le projet repart proprement avec une seule migration initiale à générer.

### Générer et appliquer les migrations

```bash
# Générer automatiquement depuis les modèles SQLAlchemy
make migrate-auto
# ou avec un message personnalisé :
make migrate-create msg="ajout_champ_xxx"

# Appliquer toutes les migrations
make migrate         # = alembic upgrade head

# Rollback d'une migration
alembic downgrade -1

# Voir l'historique
alembic history
alembic current
```

### Repartir de zéro (reset complet)

```bash
# Supprimer le volume Docker et repartir proprement
make docker-clean-dev
make docker-dev
sleep 3
make migrate-auto
make migrate
make bootstrap
make run
```

### Tables créées

| Table | Description |
|-------|-------------|
| `comptes_locaux` | **NOUVEAU** — Identité locale + credentials |
| `profils_locaux` | **REFACTORISÉ** — Inscription / dossier scolaire |
| `roles` | Rôles RBAC |
| `assignations_role` | Rôles assignés aux profils |
| `groupes` | Groupes d'utilisateurs |
| `assignations_groupe` | Membres des groupes |
| `permissions` | Permissions granulaires |
| `permission_sources` | Microservices sources de permissions |
| `delegations` | Délégations temporaires de droits |
| `journal_acces` | Audit immuable |
| `endpoint_permissions` | Mapping endpoint ↔ permission |
| `token_settings` | Configuration des tokens |
| `token_manager_records` | Historique des configurations |

---

## 9. Authentification — Guide complet

### Auth locale (username/password)

```http
POST /api/v1/tokens/login
Content-Type: application/json

{
  "username": "koffi.assoumou.E2024001",
  "password": "MonMotDePasse123!"
}
```

**Réponse :**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "session_id": "session-uuid",
  "user": {
    "id": "<profil_id>",
    "username": "koffi.assoumou.E2024001",
    "nom": "ASSOUMOU",
    "prenom": "Koffi",
    "type_profil": "etudiant"
  }
}
```

### Auth SSO IAM Central

Le token IAM Central est émis par le serveur IAM Central lors du SSO.  
Il est envoyé à IAM Local qui crée/synchronise le CompteLocal et retourne un token local.

```http
POST /api/v1/tokens/sso
Authorization: Bearer <token_iam_central>
```

### Structure du JWT local

```json
{
  "iss": "iam-local",
  "sub": "<profil.id>",
  "session_id": "<session_uuid>",
  "type_profil": "etudiant",
  "permissions": ["perm-uuid-1", "perm-uuid-2"],
  "permission_codes": ["scolarite.dossier.consulter"],
  "roles": ["etudiant.base"],
  "groupes": ["promo-l1-info-2025"],
  "is_admin": false,
  "user_id_national": "<uuid_iam_central>",
  "compte_id": "<compte_uuid>",
  "statut": "actif",
  "is_bootstrap": false,
  "token_type": "access",
  "iat": 1713351600,
  "exp": 1713353400
}
```

> **Clé** : `sub` = `profil.id` — c'est la référence universelle dans tout le système.

### Durées de vie (configurables)

| Token | Durée par défaut |
|-------|-----------------|
| Access Token | 30 minutes |
| Refresh Token | 30 jours |
| Session Redis | 24 heures |
| Token Bootstrap | 48 heures |

---

## 10. Système de permissions

### Format des codes de permission

```
domaine.ressource.action
```

Exemples :
- `iam.profil.consulter`
- `iam.compte.modifier`
- `scolarite.dossier.modifier`
- `notes.bulletin.generer`

### Permissions IAM natives

| Code | Description |
|------|-------------|
| `iam.compte.consulter` | Voir les comptes locaux |
| `iam.compte.creer` | Créer un compte |
| `iam.compte.modifier` | Modifier un compte |
| `iam.compte.suspendre` | Suspendre un compte |
| `iam.compte.supprimer` | Supprimer un compte |
| `iam.profil.consulter` | Voir les profils |
| `iam.profil.creer` | Créer un profil |
| `iam.profil.modifier` | Modifier un profil |
| `iam.profil.suspendre` | Suspendre un profil |
| `iam.profil.supprimer` | Supprimer un profil |
| `iam.role.consulter` | Voir les rôles |
| `iam.role.assigner` | Assigner un rôle |
| `iam.role.revoquer` | Révoquer un rôle |
| `iam.audit.consulter` | Lire le journal d'audit |
| `iam.admin` | Accès administrateur total |

### Sources de permissions

Chaque microservice métier déclare ses permissions au démarrage :

```bash
POST /api/v1/permissions/enregistrer
{
  "source_code": "module-scolarite",
  "permissions": [
    { "code": "scolarite.dossier.consulter", ... }
  ]
}
```

### Héritage des permissions

```
ProfilLocal
  └── AssignationRole → Role → Permissions
  └── AssignationGroupe → Groupe → Roles → Permissions
  └── Delegations reçues → Permissions spécifiques
```

Le calcul est fait par `HabilitationService` et mis en cache Redis 15 minutes.

---

## 11. API — Résumé des routes

Voir **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** pour la documentation complète avec payloads, réponses et exemples.

| Module | Routes | Description |
|--------|--------|-------------|
| **Tokens** | `POST /tokens/login` `POST /tokens/refresh` `POST /tokens/logout` `GET /tokens/sessions` | Auth, sessions, refresh |
| **Comptes** | `GET /comptes/` `GET /comptes/{id}` `GET /comptes/{id}/profils` `POST /comptes/` `PATCH` `DELETE` | CRUD CompteLocal |
| **Profils** | `GET /profils/` `GET /profils/moi` `GET /profils/{id}` `POST /profils/` `PATCH` `DELETE` `POST /{id}/roles` | CRUD ProfilLocal + rôles |
| **Rôles** | `GET /roles/` `POST /roles/` `PUT /roles/{id}` `POST /{id}/permissions/ajouter` | CRUD Rôles |
| **Groupes** | `GET /groupes/` `POST /groupes/` `POST /{id}/membres` `DELETE /{id}/membres/{mid}` | CRUD Groupes |
| **Permissions** | `GET /permissions/` `POST /permissions/enregistrer` `POST /permissions/sources` | CRUD Permissions |
| **Habilitations** | `GET /habilitations/moi` `GET /habilitations/{profil_id}` `POST /habilitations/verifier` | Calcul des droits |
| **Audit** | `GET /audit/moi` `GET /audit/` `GET /audit/profil/{id}` | Journal immuable |
| **Admin** | `GET /admin/endpoints` `GET /admin/endpoints/by-module/{code}` | Administration |
| **Gateway** | `POST /gateway/forward` `GET /gateway/modules` | Routing modules |
| **Token Config** | `GET /token-config/active` `POST /token-config/` `POST /{id}/activate` | Configuration tokens |

### URL de base

- **Développement** : `http://localhost:8002/api/v1`
- **Swagger UI** : `http://localhost:8002/docs`
- **ReDoc** : `http://localhost:8002/redoc`
- **OpenAPI JSON** : `http://localhost:8002/openapi.json`

---

## 12. Intégration avec les autres modules

### Pour un microservice métier

#### 1. Enregistrer la source et les permissions (au démarrage)

```python
import httpx

async def register_with_iam():
    async with httpx.AsyncClient() as client:
        # Enregistrer la source
        await client.post(
            "http://iam-local:8002/api/v1/permissions/sources",
            json={
                "code": "module-scolarite",
                "nom": "Module Scolarité",
                "version": "1.0.0",
                "url": "http://scolarite:8003"
            }
        )
        # Déclarer les permissions
        await client.post(
            "http://iam-local:8002/api/v1/permissions/enregistrer",
            json={
                "source_code": "module-scolarite",
                "permissions": [
                    {
                        "code": "scolarite.dossier.consulter",
                        "nom": "Consulter un dossier scolaire",
                        "domaine": "scolarite",
                        "ressource": "dossier",
                        "action": "consulter"
                    }
                ]
            }
        )
```

#### 2. Valider un token entrant

```python
import jwt

def validate_token(authorization_header: str) -> dict:
    token = authorization_header.replace("Bearer ", "")
    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=["HS256"]
    )
    profil_id        = payload["sub"]          # Référence universelle
    permission_codes = payload["permission_codes"]
    user_id_national = payload.get("user_id_national")
    compte_id        = payload.get("compte_id")
    return payload

def check_permission(payload: dict, required_code: str) -> bool:
    if "iam.admin" in payload.get("roles", []):
        return True
    return required_code in payload.get("permission_codes", [])
```

#### 3. Identifier un acteur dans les données métier

```python
# Dans les tables métier, toujours stocker profil_id (sub du JWT)
# C'est la référence universelle dans tout le système IAM Local

class DossierScolarite(Base):
    cree_par_profil_id  = Column(UUID)   # = sub du JWT de la requête
    modifie_par_profil_id = Column(UUID)

# Pour obtenir les infos de l'étudiant, utiliser l'API IAM :
# GET /api/v1/profils/{profil_id}
# → retourne nom, prénom, email, type_profil, contexte_scolaire, etc.
```

### Événements Kafka

| Topic | Émis par | Payload |
|-------|----------|---------|
| `iam.profil.cree` | IAM Local | `{profil_id, compte_id, user_id_national, type_profil}` |
| `iam.profil.suspendu` | IAM Local | `{profil_id, compte_id, raison}` |
| `iam.assignation.role_assigne` | IAM Local | `{profil_id, role_id, role_code, perimetre}` |
| `iam.assignation.role_revoque` | IAM Local | `{profil_id, role_id, raison}` |
| `iam.auth.connexion` | IAM Local | `{profil_id, user_id_national, ip_address}` |
| `iam.auth.echec` | IAM Local | `{user_id_national, raison, ip_address}` |

---

## 13. Flux métier clés

### Première inscription d'un étudiant

```
1. L'étudiant se connecte via IAM Central (SSO)
   → IAM Central émet un token JWT contenant user_id_national

2. POST /tokens/sso avec le token IAM Central
   → AuthService.creer_session()
   → CompteLocalService.get_ou_creer()
       → Crée le CompteLocal (si 1ère connexion dans cet établissement)
       → Synchronise nom, prénom, email, snapshot_iam_central
   → ProfilService.get_ou_creer()
       → Crée le ProfilLocal par défaut (type: invite ou selon IAM Central)
   → Retourne JWT local (sub = profil.id)

3. L'administration crée l'inscription officielle :
   POST /profils/sans-credentials
   {
     "compte_id": "<compte_uuid>",
     "type_profil": "etudiant",
     "contexte_scolaire": { "filiere": "L1-Informatique", ... }
   }
```

### Double inscription (même étudiant, deux filières)

```
1. CompteLocal existe déjà (Koffi ASSOUMOU)
2. POST /profils/sans-credentials avec compte_id existant
   → Crée un 2ème ProfilLocal pour la 2ème filière
3. L'étudiant voit ses 2 profils via GET /profils/moi/profils-disponibles
4. Il choisit son contexte actif → ré-authentification avec le profil cible
```

### Suspension d'un étudiant

```
# Suspendre seulement L'inscription L1 Informatique
POST /profils/{profil_id_l1}/suspendre
{ "raison": "Abandon de filière" }
→ Ce profil perd ses droits. Le profil DUT reste actif.

# Suspendre TOUT l'accès étudiant (compte entier)
POST /comptes/{compte_id}/suspendre
{ "raison": "Exclusion disciplinaire générale" }
→ Tous les profils du compte sont bloqués.
```

---

## 14. Technologies et dépendances

| Technologie | Usage | Version |
|-------------|-------|---------|
| **FastAPI** | Framework API | >= 0.100 |
| **SQLAlchemy** | ORM async | >= 2.0 |
| **Alembic** | Migrations DB | >= 1.12 |
| **PostgreSQL** | Base de données | 16 |
| **Redis** | Sessions + Cache habilitations | 7 |
| **Kafka** | Events asynchrones | 3.x |
| **PyJWT** | Gestion des tokens JWT | >= 2.8 |
| **bcrypt** | Hash des mots de passe | >= 4.0 |
| **pydantic-settings** | Configuration | >= 2.0 |
| **asyncpg** | Driver PostgreSQL async | >= 0.29 |
| **aioredis** | Client Redis async | >= 2.0 |
| **uvicorn** | Serveur ASGI | >= 0.24 |

---

## 15. Variables d'environnement

```env
# ── Application ──────────────────────────────────────────────
APP_NAME=module-02-iam-local
DEBUG=false

# ── Base de données ───────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/iam_local

# ── Redis (sessions + cache) ──────────────────────────────────
REDIS_URL=redis://localhost:6379/2

# ── Kafka (événements) ────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# ── IAM Central ───────────────────────────────────────────────
IAM_CENTRAL_URL=http://iam-central:8000
IAM_CENTRAL_JWKS_URL=http://iam-central:8000/.well-known/jwks.json
IAM_CENTRAL_TOKEN=token-service-to-service
IAM_CENTRAL_ENABLED=true
IAM_CENTRAL_SYNC_TIMEOUT_SECONDS=30
IAM_CENTRAL_CACHE_TTL_MINUTES=15

# ── JWT ───────────────────────────────────────────────────────
JWT_SECRET_KEY=votre-cle-secrete-minimum-32-caracteres-aleatoires
JWT_ALGORITHM=HS256

# ── Durées de vie des tokens ──────────────────────────────────
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
SESSION_TTL_HOURS=24
MAX_SESSIONS_PER_USER=5
SESSION_BLACKLIST_TTL_MINUTES=1440

# ── Établissement ─────────────────────────────────────────────
ETABLISSEMENT_ID=uuid-de-l-etablissement
ETABLISSEMENT_CODE=UOB

# ── URLs modules métier (Gateway) ────────────────────────────
REFERENTIEL_URL=http://referentiel:8001
SCOLARITE_URL=http://scolarite:8003
NOTES_URL=http://notes:8004
RH_URL=http://rh:8005
FINANCES_URL=http://finances:8006
BIBLIOTHEQUE_URL=http://bibliotheque:8007

# ── Sécurité ──────────────────────────────────────────────────
ENCRYPT_TOKENS=false
WEBHOOK_SECRET=
```

---

## Contacts et contribution

- **Repo** : https://github.com/amourgit/EIGEN_National_Backend_IAM_Local_V1
- **Documentation API** : [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **Swagger live** : `http://localhost:8002/docs`
