# API Reference — IAM Local (Module 02)

> **Version** : 1.0  
> **Base URL** : `http://<host>:8002/api/v1`  
> **Format** : JSON  
> **Authentification** : Bearer Token JWT  
> **Documentation Swagger** : `http://<host>:8002/docs`  

---

## Table des matières

1. [Concepts fondamentaux](#1-concepts-fondamentaux)
2. [Authentification](#2-authentification)
3. [Tokens](#3-tokens--sessions)
4. [Comptes Locaux](#4-comptes-locaux)
5. [Profils](#5-profils)
6. [Rôles](#6-rôles)
7. [Groupes](#7-groupes)
8. [Permissions](#8-permissions)
9. [Habilitations](#9-habilitations)
10. [Audit](#10-audit)
11. [Administration](#11-administration)
12. [Gateway](#12-gateway)
13. [Configuration Tokens](#13-configuration-tokens)
14. [Codes d'erreur](#14-codes-derreur)
15. [Modèles de données](#15-modèles-de-données)

---

## 1. Concepts fondamentaux

### Architecture en deux couches

```
IAM Central (national)
    ↕  SSO / Synchronisation
CompteLocal  ←── unité d'identité dans l'établissement
    └── ProfilLocal  ←── unité d'inscription / dossier scolaire
            ├── JWT sub = profil.id
            ├── Session Redis → profil.id
            ├── Permissions → profil.id
            └── Rôles       → profil.id
```

### CompteLocal vs ProfilLocal

| | CompteLocal | ProfilLocal |
|---|---|---|
| **Rôle** | Identité consolidée de l'utilisateur | Une inscription / un dossier scolaire |
| **Lien IAM Central** | `user_id_national` (UUID IAM Central) | Aucun — passe par CompteLocal |
| **Credentials** | `password_hash`, `password_salt` | Aucun |
| **Multiplicité** | 1 par utilisateur dans l'établissement | N par CompteLocal (N inscriptions) |
| **JWT sub** | ❌ | ✅ `profil.id` = sub du JWT |
| **Sessions Redis** | ❌ | ✅ liées à `profil.id` |
| **Permissions/Rôles** | ❌ | ✅ assignés au profil |
| **Audit** | ❌ | ✅ tracé via `profil.id` |

### Cas d'usage multi-profils

```
Compte: Koffi ASSOUMOU (user_id_national: abc-123)
  ├── Profil 1 → Inscription L1 Informatique   (type: etudiant)
  │     sub JWT = "profil-uuid-001"
  └── Profil 2 → Inscription DUT Réseaux       (type: etudiant)
        sub JWT = "profil-uuid-002"
```

Un étudiant se connecte avec un profil à la fois. Le token identifie quel dossier scolaire est actif.

### Flux d'authentification

```
Auth locale :
  POST /tokens/login  →  CredentialService vérifie CompteLocal.password_hash
                      →  Retourne ProfilLocal actif  →  JWT (sub=profil.id)

Auth SSO :
  POST /tokens/sso    →  Valide token IAM Central
                      →  Synchronise CompteLocal
                      →  Résout/crée ProfilLocal   →  JWT (sub=profil.id)
```

---

## 2. Authentification

Toutes les routes protégées nécessitent un header :

```http
Authorization: Bearer <access_token>
```

### Permissions système

Les permissions sont sous forme de codes : `domaine.ressource.action`

Exemples : `iam.profil.consulter`, `iam.compte.modifier`, `iam.role.assigner`

Les administrateurs (`iam.admin`) ont un bypass total sur toutes les routes.

---

## 3. Tokens / Sessions

**Base URL** : `/api/v1/tokens`

---

### `POST /tokens/login`

Authentification avec credentials locaux.

**Request Body :**
```json
{
  "username": "koffi.assoumou.E2024001",
  "password": "MonMotDePasse123!"
}
```

**Response 200 :**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "session_id": "session-uuid-...",
  "user": {
    "id": "profil-uuid-...",
    "username": "koffi.assoumou.E2024001",
    "nom": "ASSOUMOU",
    "prenom": "Koffi",
    "type_profil": "etudiant",
    "permissions": ["perm-uuid-1", "perm-uuid-2"],
    "roles": ["etudiant.base"]
  }
}
```

**Erreurs :**

| Code | Description |
|------|-------------|
| 401 | Identifiants invalides / compte verrouillé |
| 403 | Profil suspendu |

---

### `POST /tokens/refresh`

Rafraîchit un access token expiré.

**Request Body :**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response 200 :**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

---

### `POST /tokens/validate`

Valide un token et retourne ses informations.  
🔒 **Requiert authentification**

**Request Body :**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "access"
}
```

**Response 200 :**
```json
{
  "valid": true,
  "token_type": "access",
  "user_id": "profil-uuid-...",
  "session_id": "session-uuid-...",
  "permissions": ["perm-uuid-1"],
  "roles": ["etudiant.base"],
  "type_profil": "etudiant",
  "expires_at": "2026-04-17T15:30:00Z"
}
```

---

### `POST /tokens/check-authorization`

Vérifie si un token a accès à un endpoint précis.  
Utilisé par les autres microservices via le Gateway.

**Request Body :**
```json
{
  "token": "eyJ...",
  "endpoint": "/api/v1/profils/",
  "method": "GET"
}
```

---

### `POST /tokens/logout`

Invalide la session courante.  
🔒 **Requiert authentification**

**Response 200 :**
```json
{ "message": "Session terminée avec succès" }
```

---

### `GET /tokens/sessions`

Liste les sessions actives de l'utilisateur connecté.  
🔒 **Requiert authentification**

**Response 200 :**
```json
[
  {
    "id": "session-uuid-...",
    "user_id": "profil-uuid-...",
    "status": "active",
    "created_at": "2026-04-17T10:00:00Z",
    "last_activity": "2026-04-17T11:30:00Z",
    "expires_at": "2026-04-17T22:00:00Z",
    "ip_address": "192.168.1.10",
    "user_agent": "Mozilla/5.0..."
  }
]
```

---

### `DELETE /tokens/sessions/{session_id}`

Révoque une session spécifique.  
🔒 **Requiert authentification**

---

### `GET /tokens/metrics`

Métriques du système de tokens.  
🔒 **Requiert authentification** + `iam.admin`

---

### `GET /tokens/sessions/stats`

Statistiques des sessions actives.  
🔒 **Requiert authentification** + `iam.admin`

---

### `POST /tokens/sync/{user_id_national}`

Synchronise les données d'un utilisateur depuis IAM Central.  
🔒 **Requiert authentification** + `iam.admin`

---

### `GET /tokens/sync/status`

Statut de la synchronisation IAM Central.  
🔒 **Requiert authentification** + `iam.admin`

---

### `POST /tokens/change-password`

Changer le mot de passe de l'utilisateur connecté.  
🔒 **Requiert authentification**

**Request Body :**
```json
{
  "old_password": "AncienMotDePasse!",
  "new_password": "NouveauMotDePasse!123"
}
```

---

### `POST /tokens/admin/reset-password`

Réinitialiser le mot de passe d'un compte (admin).  
🔒 **Requiert** `iam.admin`

**Request Body :**
```json
{
  "compte_id": "compte-uuid-...",
  "new_password": "MotDePasseTemporaire!1"
}
```

---

## 4. Comptes Locaux

**Base URL** : `/api/v1/comptes`

Le CompteLocal représente l'identité d'un utilisateur dans l'établissement.  
Il est le seul à porter le lien avec IAM Central.

---

### `GET /comptes/`

Liste tous les comptes locaux.  
🔒 **Permission requise** : `iam.compte.consulter`

**Query params :**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `statut` | string | Filtre : `actif`, `suspendu`, `inactif`, `bootstrap` |
| `q` | string | Recherche sur nom, prénom, email, identifiant national |
| `skip` | int | Pagination offset (défaut: 0) |
| `limit` | int | Taille de page (défaut: 50, max: 200) |

**Response 200 :**
```json
[
  {
    "id": "compte-uuid-...",
    "created_at": "2026-01-15T08:00:00Z",
    "updated_at": "2026-04-17T10:00:00Z",
    "user_id_national": "iam-central-uuid-...",
    "nom": "ASSOUMOU",
    "prenom": "Koffi",
    "email": "k.assoumou@universite.ga",
    "identifiant_national": "E2024001",
    "username": "koffi.assoumou.E2024001",
    "statut": "actif",
    "derniere_connexion": "2026-04-17T10:00:00Z",
    "nb_profils": 2
  }
]
```

---

### `GET /comptes/moi`

Retourne le CompteLocal de l'utilisateur connecté.  
🔒 **Requiert authentification**

**Response 200 :** Voir [CompteLocalResponseSchema](#comptelocal-response)

---

### `GET /comptes/{compte_id}`

Détail complet d'un compte, avec le nombre de profils.  
🔒 **Permission requise** : `iam.compte.consulter`

**Response 200 :** Voir [CompteLocalResponseSchema](#comptelocal-response)

---

### `GET /comptes/{compte_id}/profils`

Tous les profils (inscriptions) d'un compte.  
🔒 **Permission requise** : `iam.compte.consulter`

**Response 200 :**
```json
[
  {
    "id": "profil-uuid-001",
    "compte_id": "compte-uuid-...",
    "type_profil": "etudiant",
    "statut": "actif",
    "contexte_scolaire": {
      "filiere": "L1-Informatique",
      "annee_academique": "2025-2026",
      "niveau": "L1"
    },
    "compte_nom": "ASSOUMOU",
    "compte_prenom": "Koffi",
    "compte_email": "k.assoumou@universite.ga",
    "compte_identifiant_national": "E2024001",
    "compte_user_id_national": "iam-central-uuid-..."
  },
  {
    "id": "profil-uuid-002",
    "compte_id": "compte-uuid-...",
    "type_profil": "etudiant",
    "statut": "actif",
    "contexte_scolaire": {
      "filiere": "DUT-Reseaux",
      "annee_academique": "2025-2026",
      "niveau": "DUT1"
    }
  }
]
```

---

### `GET /comptes/{compte_id}/profils/count`

Nombre de profils pour un compte.  
🔒 **Permission requise** : `iam.compte.consulter`

**Response 200 :**
```json
{
  "compte_id": "compte-uuid-...",
  "nb_profils": 2,
  "profils_actifs": 2
}
```

---

### `GET /comptes/recherche/par-identifiant/{identifiant_national}`

Recherche un compte par identifiant national éducatif.  
🔒 **Permission requise** : `iam.compte.consulter`

**Exemple :** `GET /comptes/recherche/par-identifiant/E2024001`

**Response 200 :** Voir [CompteLocalResponseSchema](#comptelocal-response)

---

### `GET /comptes/recherche/par-email/{email}`

Recherche un compte par adresse email.  
🔒 **Permission requise** : `iam.compte.consulter`

**Exemple :** `GET /comptes/recherche/par-email/k.assoumou@universite.ga`

---

### `GET /comptes/recherche/par-user-national/{user_id_national}`

Recherche un compte par UUID IAM Central.  
🔒 **Permission requise** : `iam.compte.consulter`

**Exemple :** `GET /comptes/recherche/par-user-national/550e8400-e29b-41d4-a716-446655440000`

---

### `GET /comptes/stats/resume`

Statistiques globales des comptes.  
🔒 **Permission requise** : `iam.compte.consulter`

**Response 200 :**
```json
{
  "total": 1250,
  "par_statut": {
    "actif": 1200,
    "suspendu": 30,
    "inactif": 18,
    "bootstrap": 1,
    "expire": 1
  }
}
```

---

### `POST /comptes/`

Crée un compte local manuellement (sans credentials, SSO uniquement).  
🔒 **Permission requise** : `iam.compte.creer`

**Request Body :**
```json
{
  "user_id_national": "550e8400-e29b-41d4-a716-446655440000",
  "nom": "ASSOUMOU",
  "prenom": "Koffi",
  "email": "k.assoumou@universite.ga",
  "telephone": "+24101234567",
  "identifiant_national": "E2024001",
  "meta_data": {},
  "notes": ""
}
```

**Response 201 :** Voir [CompteLocalResponseSchema](#comptelocal-response)

---

### `PATCH /comptes/{compte_id}`

Met à jour les informations d'un compte.  
🔒 **Permission requise** : `iam.compte.modifier`

**Request Body (champs optionnels) :**
```json
{
  "nom": "ASSOUMOU-OBIANG",
  "telephone": "+24107654321",
  "notes": "Changement de nom après mariage"
}
```

---

### `POST /comptes/{compte_id}/suspendre`

Suspend un compte (bloque tous ses profils).  
🔒 **Permission requise** : `iam.compte.suspendre`

**Request Body :**
```json
{
  "raison": "Non-paiement des frais de scolarité 2025-2026"
}
```

> ⚠️ Suspendre un compte empêche l'authentification sur TOUS ses profils associés.

---

### `POST /comptes/{compte_id}/reactiver`

Réactive un compte suspendu.  
🔒 **Permission requise** : `iam.compte.modifier`

---

### `DELETE /comptes/{compte_id}`

Soft-delete d'un compte (et de tous ses profils en cascade).  
🔒 **Permission requise** : `iam.compte.supprimer`

**Response 204 :** No Content

> ⚠️ Le compte bootstrap ne peut pas être supprimé via cette route.

---

## 5. Profils

**Base URL** : `/api/v1/profils`

Le ProfilLocal est **l'unité centrale** de tout le système IAM Local.  
Son `id` est le `sub` du JWT, la clé des sessions Redis, et la référence de toutes les permissions.

---

### `GET /profils/`

Liste tous les profils.  
🔒 **Permission requise** : `iam.profil.consulter`

**Query params :**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `type_profil` | string | `etudiant`, `enseignant`, `enseignant_chercheur`, `personnel_admin`, `personnel_technique`, `direction`, `invite`, `systeme` |
| `statut` | string | `actif`, `suspendu`, `inactif`, `expire`, `bootstrap` |
| `q` | string | Recherche full-text (nom, prénom, email, identifiant, username) |
| `skip` | int | Offset pagination |
| `limit` | int | Taille page (max 200) |

**Response 200 :**
```json
[
  {
    "id": "profil-uuid-001",
    "created_at": "2026-01-15T08:00:00Z",
    "updated_at": "2026-04-17T10:00:00Z",
    "compte_id": "compte-uuid-...",
    "username": "koffi.assoumou.E2024001",
    "type_profil": "etudiant",
    "statut": "actif",
    "derniere_connexion": "2026-04-17T10:00:00Z",
    "compte_nom": "ASSOUMOU",
    "compte_prenom": "Koffi",
    "compte_email": "k.assoumou@universite.ga",
    "compte_identifiant_national": "E2024001"
  }
]
```

---

### `GET /profils/moi`

Profil de l'utilisateur connecté (profil actif, celui du JWT).  
🔒 **Requiert authentification**

**Response 200 :** Voir [ProfilResponseSchema](#profil-response)

---

### `GET /profils/moi/profils-disponibles`

Tous les profils actifs du même compte.  
Permet à un utilisateur de voir ses autres inscriptions et de changer de contexte.  
🔒 **Requiert authentification**

**Response 200 :**
```json
[
  {
    "id": "profil-uuid-001",
    "type_profil": "etudiant",
    "contexte_scolaire": { "filiere": "L1-Informatique" },
    "statut": "actif"
  },
  {
    "id": "profil-uuid-002",
    "type_profil": "etudiant",
    "contexte_scolaire": { "filiere": "DUT-Reseaux" },
    "statut": "actif"
  }
]
```

> 💡 **Usage frontend** : afficher un sélecteur de profil. Après sélection, refaire un `/tokens/login` ou implémenter un endpoint de switch de profil.

---

### `GET /profils/{profil_id}`

Détail complet d'un profil avec identité dénormalisée du compte.  
🔒 **Permission requise** : `iam.profil.consulter`

**Response 200 :** Voir [ProfilResponseSchema](#profil-response)

---

### `GET /profils/par-compte/{compte_id}`

Tous les profils d'un compte donné.  
🔒 **Permission requise** : `iam.profil.consulter`

---

### `GET /profils/par-compte/{compte_id}/count`

Nombre de profils d'un compte avec détails par type.  
🔒 **Permission requise** : `iam.profil.consulter`

**Response 200 :**
```json
{
  "compte_id": "compte-uuid-...",
  "nb_profils": 3,
  "profils_actifs": 2,
  "par_type": {
    "etudiant": 2,
    "enseignant": 1
  }
}
```

---

### `GET /profils/par-user-national/{user_id_national}`

Tous les profils d'un utilisateur IAM Central dans cet établissement.  
Utile pour les services qui reçoivent un `user_id_national` depuis IAM Central.  
🔒 **Permission requise** : `iam.profil.consulter`

---

### `GET /profils/stats/resume`

Statistiques globales des profils.  
🔒 **Permission requise** : `iam.profil.consulter`

**Response 200 :**
```json
{
  "total": 3750,
  "par_statut": {
    "actif": 3600,
    "suspendu": 80,
    "inactif": 50,
    "expire": 20
  },
  "par_type": {
    "etudiant": 3200,
    "enseignant": 380,
    "personnel_admin": 120,
    "direction": 25,
    "systeme": 2,
    "invite": 23
  }
}
```

---

### `POST /profils/sans-credentials`

Crée un profil rattaché à un CompteLocal **existant**.  
Utilisé pour ajouter une inscription à un compte existant.  
🔒 **Permission requise** : `iam.profil.creer`

**Request Body :**
```json
{
  "compte_id": "compte-uuid-...",
  "type_profil": "etudiant",
  "contexte_scolaire": {
    "filiere": "L2-Mathematiques",
    "composante": "Sciences Exactes",
    "niveau": "L2",
    "annee_academique": "2025-2026",
    "specialite": "Mathématiques Appliquées"
  },
  "meta_data": {},
  "notes": "Inscription en double cursus"
}
```

**Response 201 :** Voir [ProfilResponseSchema](#profil-response)

---

### `POST /profils/`

Crée un **CompteLocal + ProfilLocal** en une opération, avec credentials.  
Utilisé pour les utilisateurs sans accès SSO IAM Central.  
🔒 **Permission requise** : `iam.profil.creer`

**Request Body :**
```json
{
  "nom": "MOUNDOUNGA",
  "prenom": "Brigitte",
  "email": "b.moundounga@universite.ga",
  "telephone": "+24106789012",
  "identifiant_national": "P2024050",
  "username": "brigitte.moundounga.P2024050",
  "password": "MotDePasseInitial!2024",
  "require_password_change": true,
  "type_profil": "personnel_admin",
  "classe": null,
  "niveau": null,
  "specialite": "Scolarité",
  "annee_scolaire": "2025-2026",
  "meta_data": {},
  "notes": "Personnel de la scolarité centrale"
}
```

**Response 201 :** Voir [ProfilResponseSchema](#profil-response)

---

### `PATCH /profils/{profil_id}`

Met à jour les informations d'un profil.  
🔒 **Permission requise** : `iam.profil.modifier`

**Request Body (champs optionnels) :**
```json
{
  "type_profil": "enseignant_chercheur",
  "contexte_scolaire": {
    "departement": "Informatique",
    "labo": "Labo IA"
  },
  "notes": "Passage en HDR"
}
```

---

### `POST /profils/{profil_id}/suspendre`

Suspend un profil spécifique.  
🔒 **Permission requise** : `iam.profil.suspendre`

**Request Body :**
```json
{
  "raison": "Exclusion disciplinaire temporaire - 1 mois"
}
```

> ℹ️ Contrairement à la suspension du compte, seul CE profil est bloqué. Les autres profils du même compte restent accessibles.

---

### `POST /profils/{profil_id}/reactiver`

Réactive un profil suspendu.  
🔒 **Permission requise** : `iam.profil.modifier`

---

### `DELETE /profils/{profil_id}`

Soft-delete d'un profil.  
🔒 **Permission requise** : `iam.profil.supprimer`

**Response 204 :** No Content

---

### `POST /profils/{profil_id}/roles`

Assigne un rôle à un profil.  
🔒 **Permission requise** : `iam.role.assigner`

**Request Body :**
```json
{
  "role_id": "role-uuid-...",
  "perimetre": {
    "composante_id": "composante-uuid-...",
    "annee_academique": "2025-2026"
  },
  "date_debut": "2026-01-01T00:00:00Z",
  "date_fin": "2026-12-31T23:59:59Z",
  "raison_assignation": "Tuteur pédagogique L1 Informatique"
}
```

**Response 201 :**
```json
{
  "id": "assignation-uuid-...",
  "profil_id": "profil-uuid-...",
  "role_id": "role-uuid-...",
  "statut": "active",
  "perimetre": { "composante_id": "..." },
  "date_debut": "2026-01-01T00:00:00Z",
  "date_fin": "2026-12-31T23:59:59Z"
}
```

---

### `DELETE /profils/roles/{assignation_id}`

Révoque une assignation de rôle.  
🔒 **Permission requise** : `iam.role.revoquer`

**Request Body :**
```json
{
  "raison_revocation": "Fin de mission tuteur"
}
```

**Response 204 :** No Content

---

## 6. Rôles

**Base URL** : `/api/v1/roles`

---

### `GET /roles/`

Liste tous les rôles.  
🔒 **Permission requise** : `iam.role.consulter`

**Response 200 :**
```json
[
  {
    "id": "role-uuid-...",
    "code": "etudiant.base",
    "nom": "Étudiant de base",
    "description": "Accès aux ressources pédagogiques standard",
    "type": "fonctionnel",
    "perimetre_obligatoire": false,
    "actif": true,
    "nb_permissions": 12
  }
]
```

---

### `POST /roles/`

Crée un rôle.  
🔒 **Permission requise** : `iam.role.creer`

**Request Body :**
```json
{
  "code": "tuteur.pedagogique",
  "nom": "Tuteur Pédagogique",
  "description": "Accès au suivi des étudiants tutorés",
  "type": "fonctionnel",
  "perimetre_obligatoire": true,
  "meta_data": {}
}
```

---

### `GET /roles/{role_id}`

Détail d'un rôle avec la liste de ses permissions.  
🔒 **Permission requise** : `iam.role.consulter`

---

### `PUT /roles/{role_id}`

Met à jour un rôle.  
🔒 **Permission requise** : `iam.role.modifier`

---

### `POST /roles/{role_id}/permissions/ajouter`

Ajoute des permissions à un rôle.  
🔒 **Permission requise** : `iam.role.modifier`

**Request Body :**
```json
{
  "permission_ids": [
    "perm-uuid-001",
    "perm-uuid-002"
  ]
}
```

---

### `POST /roles/{role_id}/permissions/retirer`

Retire des permissions d'un rôle.  
🔒 **Permission requise** : `iam.role.modifier`

---

### `DELETE /roles/{role_id}`

Supprime un rôle (soft delete).  
🔒 **Permission requise** : `iam.role.supprimer`

---

## 7. Groupes

**Base URL** : `/api/v1/groupes`

Les groupes permettent d'assigner des rôles à plusieurs profils simultanément.

---

### `GET /groupes/`

Liste tous les groupes.  
🔒 **Permission requise** : `iam.groupe.consulter`

**Response 200 :**
```json
[
  {
    "id": "groupe-uuid-...",
    "code": "promo-l1-info-2025",
    "nom": "Promotion L1 Informatique 2025-2026",
    "type": "organisationnel",
    "description": "Tous les étudiants L1 Info de l'année 2025-2026",
    "perimetre": { "filiere": "L1-Informatique", "annee": "2025-2026" },
    "nb_membres": 87
  }
]
```

---

### `POST /groupes/`

Crée un groupe.  
🔒 **Permission requise** : `iam.groupe.creer`

**Request Body :**
```json
{
  "code": "promo-l1-info-2025",
  "nom": "Promotion L1 Informatique 2025-2026",
  "type": "organisationnel",
  "description": "...",
  "perimetre": { "filiere": "L1-Informatique" }
}
```

---

### `GET /groupes/{groupe_id}`

Détail d'un groupe avec ses rôles et membres.  
🔒 **Permission requise** : `iam.groupe.consulter`

---

### `PUT /groupes/{groupe_id}`

Modifie un groupe.  
🔒 **Permission requise** : `iam.groupe.modifier`

---

### `POST /groupes/{groupe_id}/roles/ajouter`

Ajoute des rôles à un groupe (tous les membres héritent des rôles).  
🔒 **Permission requise** : `iam.groupe.modifier`

**Request Body :**
```json
{
  "role_ids": ["role-uuid-001"]
}
```

---

### `DELETE /groupes/{groupe_id}/roles/{role_id}`

Retire un rôle d'un groupe.  
🔒 **Permission requise** : `iam.groupe.modifier`

---

### `POST /groupes/{groupe_id}/membres`

Ajoute un profil comme membre d'un groupe.  
🔒 **Permission requise** : `iam.groupe.membre.ajouter`

**Request Body :**
```json
{
  "profil_id": "profil-uuid-...",
  "date_debut": "2026-01-01T00:00:00Z",
  "date_fin": null,
  "raison": "Inscription L1 Informatique 2025-2026"
}
```

---

### `DELETE /groupes/{groupe_id}/membres/{assignation_id}`

Retire un membre d'un groupe.  
🔒 **Permission requise** : `iam.groupe.membre.ajouter`

---

### `DELETE /groupes/{groupe_id}`

Supprime un groupe.  
🔒 **Permission requise** : `iam.groupe.supprimer`

---

## 8. Permissions

**Base URL** : `/api/v1/permissions`

---

### `GET /permissions/`

Liste toutes les permissions.  
🔒 **Permission requise** : `iam.permission.consulter`

**Query params :**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `domaine` | string | Filtre par domaine (ex: `scolarite`, `iam`) |
| `source_code` | string | Filtre par microservice source |
| `actif` | bool | `true` / `false` |

**Response 200 :**
```json
[
  {
    "id": "perm-uuid-...",
    "code": "scolarite.dossier.consulter",
    "nom": "Consulter un dossier de scolarité",
    "domaine": "scolarite",
    "ressource": "dossier",
    "action": "consulter",
    "actif": true,
    "source": { "code": "module-scolarite", "nom": "Module Scolarité" }
  }
]
```

---

### `POST /permissions/sources`

Enregistre un microservice comme source de permissions.  
Appelé par les modules métier au démarrage.

**Request Body :**
```json
{
  "code": "module-scolarite",
  "nom": "Module Scolarité",
  "description": "Gestion des inscriptions et dossiers scolaires",
  "version": "1.0.0",
  "url": "http://scolarite:8003"
}
```

---

### `GET /permissions/sources`

Liste les microservices enregistrés.

---

### `POST /permissions/enregistrer`

Enregistre en masse les permissions d'un microservice.  
Idempotent — met à jour si la permission existe déjà.

**Request Body :**
```json
{
  "source_code": "module-scolarite",
  "permissions": [
    {
      "code": "scolarite.dossier.consulter",
      "nom": "Consulter un dossier",
      "domaine": "scolarite",
      "ressource": "dossier",
      "action": "consulter"
    },
    {
      "code": "scolarite.dossier.modifier",
      "nom": "Modifier un dossier",
      "domaine": "scolarite",
      "ressource": "dossier",
      "action": "modifier"
    }
  ]
}
```

---

### `POST /permissions/`

Crée une permission manuellement.  
🔒 **Permission requise** : `iam.permission.creer`

---

### `GET /permissions/{permission_id}`

Détail d'une permission.  
🔒 **Permission requise** : `iam.permission.consulter`

---

### `PUT /permissions/{permission_id}`

Modifie une permission.  
🔒 **Permission requise** : `iam.permission.modifier`

---

## 9. Habilitations

**Base URL** : `/api/v1/habilitations`

Les habilitations sont le calcul complet des droits effectifs d'un profil :
- Rôles directs
- Rôles via groupes
- Délégations reçues actives

Le résultat est mis en cache Redis **15 minutes**.

---

### `GET /habilitations/moi`

Habilitations complètes de l'utilisateur connecté.  
🔒 **Requiert authentification**

**Response 200 :**
```json
{
  "profil_id": "profil-uuid-...",
  "user_id_national": "iam-central-uuid-...",
  "type_profil": "etudiant",
  "statut": "actif",
  "permissions": [
    {
      "id": "perm-uuid-...",
      "code": "scolarite.dossier.consulter",
      "nom": "Consulter un dossier",
      "domaine": "scolarite",
      "ressource": "dossier",
      "action": "consulter",
      "perimetre": { "filiere": "L1-Informatique" },
      "source": "role:etudiant.base"
    }
  ],
  "roles_actifs": ["etudiant.base"],
  "groupes_actifs": ["promo-l1-info-2025"]
}
```

---

### `GET /habilitations/{profil_id}`

Habilitations d'un profil spécifique.  
🔒 **Permission requise** : `iam.profil.consulter`

---

### `POST /habilitations/verifier`

Vérifie si l'utilisateur connecté a une permission donnée.  
🔒 **Requiert authentification**

**Request Body :**
```json
{
  "permission_code": "scolarite.dossier.modifier",
  "perimetre": {
    "filiere_id": "filiere-uuid-...",
    "annee_academique": "2025-2026"
  }
}
```

**Response 200 :**
```json
{
  "autorise": true,
  "permission_code": "scolarite.dossier.modifier",
  "raison": "Permission accordée via rôle etudiant.base"
}
```

---

### `POST /habilitations/{profil_id}/verifier`

Vérifie une permission pour un profil spécifique.  
🔒 **Permission requise** : `iam.profil.consulter`

---

### `DELETE /habilitations/{profil_id}/cache`

Invalide le cache Redis des habilitations d'un profil.  
À utiliser après modification des rôles/permissions d'un profil.  
🔒 **Permission requise** : `iam.profil.modifier`

**Response 200 :**
```json
{ "message": "Cache des habilitations invalidé" }
```

---

## 10. Audit

**Base URL** : `/api/v1/audit`

Journal immuable de toutes les actions. Non soft-deletable par conception.

---

### `GET /audit/moi`

Journal d'activité de l'utilisateur connecté.  
🔒 **Requiert authentification**

**Query params :**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `skip` | int | Offset |
| `limit` | int | Taille (max 200) |
| `type_action` | string | `connexion`, `deconnexion`, `acces_autorise`, etc. |

**Response 200 :**
```json
[
  {
    "id": "journal-uuid-...",
    "timestamp": "2026-04-17T10:00:00Z",
    "type_action": "connexion",
    "profil_id": "profil-uuid-...",
    "user_id_national": "iam-central-uuid-...",
    "nom_affiche": "Koffi ASSOUMOU",
    "module": "iam",
    "ressource": "auth",
    "action": "login",
    "autorise": true,
    "ip_address": "192.168.1.10",
    "session_id": "session-uuid-..."
  }
]
```

---

### `GET /audit/`

Journal d'audit global (tous les profils).  
🔒 **Permission requise** : `iam.audit.consulter`

---

### `GET /audit/profil/{profil_id}`

Journal d'activité d'un profil spécifique.  
🔒 **Permission requise** : `iam.audit.consulter`

---

## 11. Administration

**Base URL** : `/api/v1/admin`

---

### `GET /admin/endpoints`

Liste tous les endpoints enregistrés de tous les modules avec leurs permissions.  
🔒 **Permission requise** : `iam.admin`

---

### `GET /admin/endpoints/by-module/{module_code}`

Endpoints d'un module spécifique.  
🔒 **Permission requise** : `iam.admin`

---

### `POST /endpoints/register`

Enregistre les endpoints d'un module (appelé par les modules au démarrage).

**Request Body :**
```json
{
  "module_code": "module-scolarite",
  "module_nom": "Module Scolarité",
  "endpoints": [
    {
      "path": "/api/v1/inscriptions/{id}",
      "method": "GET",
      "permission_code": "scolarite.inscription.consulter",
      "description": "Consulter une inscription"
    }
  ]
}
```

---

### `GET /endpoints/`

Liste les endpoints enregistrés avec leurs permissions associées.  
🔒 **Permission requise** : `iam.admin`

---

## 12. Gateway

**Base URL** : `/api/v1/gateway`

Le gateway route les requêtes vers les modules métier après vérification des permissions.

---

### `POST /gateway/forward`

Route une requête vers un module métier.

**Request Body :**
```json
{
  "module": "scolarite",
  "path": "/inscriptions/",
  "method": "GET",
  "body": null,
  "query_params": { "annee": "2025-2026" }
}
```

---

### `GET /gateway/modules`

Liste les modules connus du gateway et leur statut.

**Response 200 :**
```json
[
  {
    "code": "scolarite",
    "nom": "Module Scolarité",
    "url": "http://scolarite:8003",
    "statut": "actif"
  }
]
```

---

## 13. Configuration Tokens

**Base URL** : `/api/v1/token-config`

---

### `GET /token-config/active`

Configuration active des tokens (durées de vie, limites).  
🔒 **Permission requise** : `iam.admin`

**Response 200 :**
```json
{
  "id": "config-uuid-...",
  "access_token_lifetime_minutes": 30,
  "refresh_token_lifetime_days": 30,
  "session_ttl_hours": 24,
  "max_sessions_per_user": 5,
  "actif": true
}
```

---

### `POST /token-config/`

Crée une nouvelle configuration.  
🔒 **Permission requise** : `iam.admin`

---

### `GET /token-config/`

Historique de toutes les configurations.  
🔒 **Permission requise** : `iam.admin`

---

### `PUT /token-config/{config_id}`

Met à jour une configuration existante.  
🔒 **Permission requise** : `iam.admin`

---

### `POST /token-config/{config_id}/activate`

Active une configuration (désactive l'ancienne active).  
🔒 **Permission requise** : `iam.admin`

---

### `DELETE /token-config/{config_id}`

Supprime une configuration.  
🔒 **Permission requise** : `iam.admin`

---

### `POST /token-config/refresh-cache`

Force le rechargement du cache de configuration depuis la base.  
🔒 **Permission requise** : `iam.admin`

---

## 14. Codes d'erreur

| Code HTTP | Code interne | Description |
|-----------|-------------|-------------|
| 400 | `VALIDATION_ERROR` | Données de requête invalides |
| 401 | `UNAUTHORIZED` | Token absent ou invalide |
| 401 | `TOKEN_EXPIRED` | Token expiré |
| 403 | `FORBIDDEN` | Accès interdit (bootstrap limité) |
| 403 | `PERMISSION_DENIED` | Permission manquante |
| 404 | `NOT_FOUND` | Ressource introuvable |
| 409 | `ALREADY_EXISTS` | Ressource déjà existante (doublon) |
| 422 | `UNPROCESSABLE_ENTITY` | Erreur de validation Pydantic |
| 429 | `RATE_LIMITED` | Trop de requêtes |
| 500 | `INTERNAL_ERROR` | Erreur serveur |

**Format d'erreur :**
```json
{
  "detail": "Profil introuvable : profil-uuid-...",
  "code": "NOT_FOUND",
  "resource": "Profil"
}
```

---

## 15. Modèles de données

### CompteLocal Response

```json
{
  "id": "uuid",
  "created_at": "datetime",
  "updated_at": "datetime",
  "created_by": "uuid | null",
  "updated_by": "uuid | null",
  "user_id_national": "uuid | null",
  "nom": "string | null",
  "prenom": "string | null",
  "email": "string | null",
  "telephone": "string | null",
  "identifiant_national": "string | null",
  "username": "string | null",
  "statut": "actif | inactif | suspendu | expire | bootstrap",
  "raison_suspension": "string | null",
  "derniere_connexion": "datetime | null",
  "nb_connexions": "string | null",
  "premiere_connexion": "datetime | null",
  "require_password_change": "bool",
  "has_credentials": "bool",
  "nb_profils": "int | null",
  "preferences": "object",
  "meta_data": "object",
  "notes": "string | null"
}
```

### Profil Response

```json
{
  "id": "uuid",
  "created_at": "datetime",
  "updated_at": "datetime",
  "created_by": "uuid | null",
  "updated_by": "uuid | null",
  "compte_id": "uuid",
  "username": "string | null",
  "type_profil": "etudiant | enseignant | enseignant_chercheur | personnel_admin | personnel_technique | direction | invite | systeme",
  "statut": "actif | inactif | suspendu | expire | bootstrap",
  "raison_suspension": "string | null",
  "derniere_connexion": "datetime | null",
  "nb_connexions": "string | null",
  "premiere_connexion": "datetime | null",
  "contexte_scolaire": {
    "filiere": "string",
    "composante": "string",
    "departement": "string",
    "annee_academique": "string",
    "niveau": "string",
    "specialite": "string",
    "numero_etudiant_local": "string"
  },
  "preferences": "object",
  "meta_data": "object",
  "notes": "string | null",
  "require_password_change": "bool | null",
  "compte_nom": "string | null",
  "compte_prenom": "string | null",
  "compte_email": "string | null",
  "compte_telephone": "string | null",
  "compte_identifiant_national": "string | null",
  "compte_user_id_national": "uuid | null"
}
```

### JWT Payload

```json
{
  "iss": "iam-local",
  "sub": "<profil_id>",
  "iat": 1713351600,
  "exp": 1713353400,
  "jti": "<session_id>",
  "session_id": "<session_id>",
  "type_profil": "etudiant",
  "permissions": ["perm-uuid-1", "perm-uuid-2"],
  "permission_codes": ["scolarite.dossier.consulter"],
  "roles": ["etudiant.base"],
  "is_admin": false,
  "token_type": "access",
  "version": "1.0",
  "user_id_national": "<uuid iam central | null>",
  "statut": "actif",
  "groupes": ["promo-l1-info-2025"],
  "compte_id": "<compte_id>",
  "is_bootstrap": false
}
```

---

## Notes d'intégration

### Pour les équipes Frontend

1. **Stocker** `access_token` + `refresh_token` en mémoire (pas localStorage en prod).
2. **Rafraîchir** automatiquement via `POST /tokens/refresh` quand le 401 arrive.
3. **Changer de profil** : récupérer les profils disponibles via `GET /profils/moi/profils-disponibles`, puis ré-authentifier avec le profil cible.
4. **Vérifier les permissions** localement via les `permission_codes` du JWT plutôt que des appels API répétés.

### Pour les équipes Backend / Microservices

1. **Enregistrer les permissions** au démarrage via `POST /permissions/enregistrer`.
2. **Enregistrer les endpoints** via `POST /endpoints/register`.
3. **Vérifier les accès** via `POST /tokens/check-authorization` ou décoder le JWT localement.
4. **Le champ `sub` du JWT = `profil.id`** — c'est la référence universelle pour identifier un acteur dans les logs et les données métier.
5. **Invalider le cache** après modification des rôles : `DELETE /habilitations/{profil_id}/cache`.
