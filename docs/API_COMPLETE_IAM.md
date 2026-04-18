# Documentation Complète des API IAM Local

## Table des Matières

1. [Introduction](#introduction)
2. [Architecture](#architecture)
3. [Modules d'API](#modules-dapi)
   - [Authentification & Tokens](#authentification--tokens)
   - [Profils](#profils)
   - [Permissions](#permissions)
   - [Rôles](#rôles)
   - [Groupes](#groupes)
   - [Habilitations](#habilitations)
   - [Audit](#audit)
   - [Endpoints](#endpoints)
   - [Admin](#admin)
   - [Gateway](#gateway)
   - [Configuration Tokens](#configuration-tokens)
4. [Variables de Test](#variables-de-test)
5. [Scénarios de Test Complet](#scénarios-de-test-complet)

---

## Introduction

Ce document présente toutes les API du microservice IAM Local de EGEN. Le service IAM gère l'authentification, les autorisations, les profils utilisateurs et le routage vers les autres microservices.

### Base URL
```
http://localhost:8000/api/v1
```

### Authentification
Toutes les API (sauf celles explicitement publiques) nécessitent un token JWT dans l'en-tête :
```
Authorization: Bearer <votre_token_jwt>
```

---

## Architecture

### Flux d'Authentification
1. **Login** : `POST /tokens/login` avec credentials locaux
2. **Token JWT** : Retourne access_token + refresh_token
3. **Utilisation** : Include Authorization: Bearer <token>
4. **Refresh** : `POST /tokens/refresh` pour renouveler
5. **Logout** : `POST /tokens/logout` pour révoquer

### Gateway Pattern
Le frontend utilise le gateway pour toutes les requêtes vers les modules métier :
```
POST /gateway/forward
{
  "module": "scolarite",
  "path": "/api/v1/etudiants",
  "method": "GET",
  "body": {...},
  "params": {...}
}
```

---

## Modules d'API

### Authentification & Tokens

#### 1. Login - Connexion
```http
POST /tokens/login
```

**Body:**
```json
{
  "username": "etudiant001",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### 2. Refresh Token
```http
POST /tokens/refresh
```

**Body:**
```json
{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### 3. Validate Token
```http
POST /tokens/validate
```

**Body:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "access"
}
```

#### 4. Logout
```http
POST /tokens/logout
```

#### 5. Mes Sessions
```http
GET /tokens/sessions
```

#### 6. Révoquer Session
```http
DELETE /tokens/sessions/{session_id}
```

#### 7. Changer Mot de Passe
```http
POST /tokens/change-password
```

**Body:**
```json
{
  "old_password": "ancien_password",
  "new_password": "nouveau_password"
}
```

#### 8. Reset Password (Admin)
```http
POST /tokens/admin/reset-password
```

**Body:**
```json
{
  "profil_id": "uuid-du-profil",
  "temp_password": "temp123!"
}
```

---

### Profils

#### 1. Créer Profil Manuel
```http
POST /profils/sans-credentials
```

**Body:**
```json
{
  "user_id_national": "uuid-national",
  "nom": "Dupont",
  "prenom": "Jean",
  "email": "jean.dupont@example.com",
  "telephone": "+33612345678",
  "identifiant_national": "ETU001",
  "type_profil": "ETUDIANT",
  "meta_data": {},
  "notes": "Étudiant en informatique"
}
```

#### 2. Créer Profil avec Credentials
```http
POST /profils/
```

**Body:**
```json
{
  "nom": "Durand",
  "prenom": "Marie",
  "email": "marie.durand@example.com",
  "telephone": "+33687654321",
  "identifiant_national": "ENS001",
  "type_profil": "ENSEIGNANT",
  "username": "marie.durand",
  "password": "password123!",
  "require_password_change": true,
  "classe": null,
  "niveau": null,
  "specialite": "Informatique",
  "annee_scolaire": null
}
```

#### 3. Lister les Profils
```http
GET /profils?type_profil=ETUDIANT&statut=ACTIF&q=dupont&skip=0&limit=50
```

#### 4. Mon Profil
```http
GET /profils/moi
```

#### 5. Détail Profil
```http
GET /profils/{profil_id}
```

#### 6. Modifier Profil
```http
PUT /profils/{profil_id}
```

**Body:**
```json
{
  "nom": "Dupont",
  "prenom": "Jean",
  "email": "jean.dupont@newmail.com",
  "telephone": "+33612345678",
  "identifiant_national": "ETU001",
  "type_profil": "ETUDIANT",
  "preferences": {},
  "meta_data": {},
  "notes": "Notes mises à jour"
}
```

#### 7. Suspendre Profil
```http
POST /profils/{profil_id}/suspendre
```

**Body:**
```json
{
  "raison": "Suspension temporaire pour révision"
}
```

#### 8. Réactiver Profil
```http
POST /profils/{profil_id}/reactiver
```

#### 9. Supprimer Profil (Soft Delete)
```http
DELETE /profils/{profil_id}
```

#### 10. Assigner Rôle à Profil
```http
POST /profils/{profil_id}/roles
```

**Body:**
```json
{
  "role_id": "uuid-du-role",
  "perimetre": {},
  "raison": "Assignation rôle étudiant"
}
```

#### 11. Lister Rôles du Profil
```http
GET /profils/{profil_id}/roles
```

#### 12. Révoquer Rôle du Profil
```http
DELETE /profils/{profil_id}/roles/{assignation_id}
```

**Body:**
```json
{
  "raison": "Changement de rôle"
}
```

---

### Permissions

#### 1. Enregistrer Source de Permissions
```http
POST /permissions/sources
```

**Body:**
```json
{
  "code": "scolarite",
  "nom": "Module Scolarité",
  "description": "Gestion de la scolarité",
  "version": "1.0.0",
  "url_base": "http://localhost:8001",
  "meta_data": {},
  "notes": "Module principal de scolarité"
}
```

#### 2. Lister Sources
```http
GET /permissions/sources
```

#### 3. Enregistrement Masse Permissions
```http
POST /permissions/enregistrer
```

**Body:**
```json
{
  "source_code": "scolarite",
  "source_nom": "Module Scolarité",
  "source_version": "1.0.0",
  "source_url": "http://localhost:8001",
  "permissions": [
    {
      "code": "scolarite.inscription.creer",
      "nom": "Créer une inscription",
      "description": "Permet de créer une nouvelle inscription",
      "domaine": "scolarite",
      "ressource": "inscription",
      "action": "creer",
      "niveau_risque": "MOYEN",
      "necessite_perimetre": false,
      "exemple_perimetre": null,
      "meta_data": {},
      "notes": null
    }
  ]
}
```

#### 4. Créer Permission Manuelle
```http
POST /permissions/
```

**Body:**
```json
{
  "source_id": null,
  "code": "iam.admin.utilisateur",
  "nom": "Administration utilisateurs",
  "description": "Permission d'administration des utilisateurs",
  "domaine": "iam",
  "ressource": "admin",
  "action": "utilisateur",
  "niveau_risque": "ELEVE",
  "necessite_perimetre": false,
  "exemple_perimetre": null,
  "meta_data": {},
  "notes": "Permission système"
}
```

#### 5. Créer Permission Custom
```http
POST /permissions/custom
```

**Body:**
```json
{
  "code": "custom.permission",
  "nom": "Permission personnalisée",
  "description": "Description de la permission",
  "domaine": "custom",
  "ressource": "resource",
  "action": "action",
  "niveau_risque": "MOYEN",
  "necessite_perimetre": false,
  "exemple_perimetre": null,
  "meta_data": {},
  "notes": null
}
```

#### 6. Lister Permissions
```http
GET /permissions?domaine=scolarite&q=inscription&skip=0&limit=100
```

#### 7. Détail Permission
```http
GET /permissions/{permission_id}
```

#### 8. Modifier Permission
```http
PUT /permissions/{permission_id}
```

**Body:**
```json
{
  "nom": "Nouveau nom",
  "description": "Nouvelle description",
  "niveau_risque": "ELEVE",
  "necessite_perimetre": true,
  "actif": true,
  "deprecated": false,
  "exemple_perimetre": {"classe": "A", "niveau": "L1"},
  "meta_data": {},
  "notes": "Notes mises à jour"
}
```

---

### Rôles

#### 1. Créer Rôle
```http
POST /roles/
```

**Body:**
```json
{
  "code": "etudiant",
  "nom": "Étudiant",
  "description": "Rôle de base pour les étudiants",
  "type_role": "FONCTIONNEL",
  "perimetre_obligatoire": false,
  "perimetre_schema": null,
  "permissions_ids": [],
  "meta_data": {},
  "notes": "Rôle étudiant standard"
}
```

#### 2. Lister Rôles
```http
GET /roles?type_role=FONCTIONNEL&q=etudiant&skip=0&limit=50
```

#### 3. Détail Rôle
```http
GET /roles/{role_id}
```

#### 4. Modifier Rôle
```http
PUT /roles/{role_id}
```

**Body:**
```json
{
  "nom": "Étudiant Avancé",
  "description": "Rôle pour les étudiants avancés",
  "type_role": "FONCTIONNEL",
  "perimetre_obligatoire": true,
  "perimetre_schema": {"classe": "string", "niveau": "string"},
  "actif": true,
  "meta_data": {},
  "notes": "Mise à jour du rôle"
}
```

#### 5. Ajouter Permissions au Rôle
```http
POST /roles/{role_id}/permissions/ajouter
```

**Body:**
```json
{
  "permissions_ids": ["uuid-permission-1", "uuid-permission-2"],
  "raison": "Ajout permissions consultation"
}
```

#### 6. Retirer Permissions du Rôle
```http
POST /roles/{role_id}/permissions/retirer
```

**Body:**
```json
{
  "permissions_ids": ["uuid-permission-1"],
  "raison": "Retrait permission obsolète"
}
```

#### 7. Supprimer Rôle
```http
DELETE /roles/{role_id}
```

---

### Groupes

#### 1. Créer Groupe
```http
POST /groupes/
```

**Body:**
```json
{
  "code": "classe_L1_info",
  "nom": "Classe L1 Informatique",
  "description": "Groupe pour les étudiants de L1 info",
  "type_groupe": "FONCTIONNEL",
  "perimetre": {"classe": "L1", "specialite": "informatique"},
  "roles_ids": [],
  "meta_data": {},
  "notes": "Groupe académique"
}
```

#### 2. Lister Groupes
```http
GET /groupes?type_groupe=FONCTIONNEL&skip=0&limit=50
```

#### 3. Détail Groupe
```http
GET /groupes/{groupe_id}
```

#### 4. Modifier Groupe
```http
PUT /groupes/{groupe_id}
```

**Body:**
```json
{
  "nom": "Classe L1 Informatique Mise à Jour",
  "description": "Description mise à jour",
  "type_groupe": "FONCTIONNEL",
  "perimetre": {"classe": "L1", "specialite": "informatique", "annee": "2024"},
  "actif": true,
  "meta_data": {},
  "notes": "Notes mises à jour"
}
```

#### 5. Ajouter Rôles au Groupe
```http
POST /groupes/{groupe_id}/roles/ajouter
```

**Body:**
```json
{
  "roles_ids": ["uuid-role-1", "uuid-role-2"],
  "perimetre": {"classe": "L1"},
  "raison": "Assignation rôle étudiant"
}
```

#### 6. Retirer Rôle du Groupe
```http
DELETE /groupes/{groupe_id}/roles/{role_id}
```

#### 7. Ajouter Membre au Groupe
```http
POST /groupes/{groupe_id}/membres
```

**Body:**
```json
{
  "profil_id": "uuid-profil",
  "perimetre": {"classe": "L1"},
  "raison": "Inscription dans la classe"
}
```

#### 8. Retirer Membre du Groupe
```http
DELETE /groupes/{groupe_id}/membres/{assignation_id}?raison=Transfert
```

#### 9. Supprimer Groupe
```http
DELETE /groupes/{groupe_id}
```

---

### Habilitations

#### 1. Mes Habilitations
```http
GET /habilitations/moi
```

#### 2. Habilitations d'un Profil
```http
GET /habilitations/{profil_id}
```

#### 3. Vérifier Permission
```http
POST /habilitations/verifier
```

**Body:**
```json
{
  "permission_code": "scolarite.inscription.creer",
  "perimetre": {"classe": "L1"},
  "contexte": {"module": "scolarite"}
}
```

#### 4. Vérifier Permission pour Profil Spécifique
```http
POST /habilitations/{profil_id}/verifier
```

**Body:**
```json
{
  "permission_code": "scolarite.inscription.consulter",
  "perimetre": {"classe": "L1"},
  "contexte": {"module": "scolarite"}
}
```

#### 5. Invalider Cache Habilitations
```http
DELETE /habilitations/{profil_id}/cache
```

---

### Audit

#### 1. Mon Journal d'Activité
```http
GET /audit/moi?skip=0&limit=50
```

#### 2. Journal d'Audit Global
```http
GET /audit?profil_id=uuid&user_id_national=uuid&type_action=CREATE&module=scolarite&autorise=true&date_debut=2024-01-01T00:00:00Z&date_fin=2024-12-31T23:59:59Z&ip_address=127.0.0.1&skip=0&limit=500
```

#### 3. Journal d'Activité d'un Profil
```http
GET /audit/profil/{profil_id}?skip=0&limit=200
```

---

### Endpoints

#### 1. Enregistrer Endpoints
```http
POST /endpoints/register
```

**Body:**
```json
{
  "source_code": "scolarite",
  "source_nom": "Module Scolarité",
  "source_version": "1.0.0",
  "endpoints": [
    {
      "path": "/api/v1/inscriptions",
      "method": "POST",
      "permission_codes": ["scolarite.inscription.creer"],
      "public": false,
      "description": "Créer une nouvelle inscription"
    }
  ]
}
```

#### 2. Lister Endpoints Enregistrés
```http
GET /endpoints/
```

---

### Admin

#### 1. Lister Tous les Endpoints avec Permissions
```http
GET /admin/endpoints?module=scolarite
```

#### 2. Lister Endpoints d'un Module
```http
GET /admin/endpoints/by-module/{module_code}
```

---

### Gateway

#### 1. Router Requête vers Module Métier
```http
POST /gateway/forward
```

**Body:**
```json
{
  "module": "scolarite",
  "path": "/api/v1/inscriptions",
  "method": "POST",
  "body": {
    "etudiant_id": "uuid-etudiant",
    "classe": "L1",
    "specialite": "informatique"
  },
  "params": {
    "validation": "true"
  },
  "headers": {
    "X-Custom-Header": "value"
  }
}
```

#### 2. Lister Modules Connus
```http
GET /gateway/modules
```

**Response:**
```json
{
  "modules": [
    {
      "code": "scolarite",
      "url": "http://localhost:8001"
    },
    {
      "code": "notes",
      "url": "http://localhost:8002"
    }
  ]
}
```

---

### Configuration Tokens

#### 1. Créer Configuration Token
```http
POST /token-config/
```

**Body:**
```json
{
  "access_token_lifetime": 3600,
  "refresh_token_lifetime": 86400,
  "issuer": "iam-local",
  "algorithm": "HS256",
  "require_password_change_days": 90,
  "max_sessions_per_user": 3,
  "session_timeout": 7200,
  "settings": {}
}
```

#### 2. Configuration Active
```http
GET /token-config/active
```

#### 3. Historique Configurations
```http
GET /token-config/?skip=0&limit=50
```

#### 4. Configuration par ID
```http
GET /token-config/{config_id}
```

#### 5. Mettre à Jour Configuration
```http
PUT /token-config/{config_id}
```

**Body:**
```json
{
  "access_token_lifetime": 7200,
  "refresh_token_lifetime": 172800,
  "max_sessions_per_user": 5
}
```

#### 6. Activer Configuration
```http
POST /token-config/{config_id}/activate
```

**Body:**
```json
{
  "version_comment": "Activation configuration v2.0"
}
```

#### 7. Supprimer Configuration
```http
DELETE /token-config/{config_id}
```

#### 8. Rafraîchir Cache Configuration
```http
POST /token-config/refresh-cache
```

---

## Variables de Test

### Variables d'Environnement
```bash
# Configuration
IAM_BASE_URL="http://localhost:8000/api/v1"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin123"

# Variables pour les tests
ETUDIANT_USERNAME="etudiant001"
ETUDIANT_PASSWORD="password123"
ENSEIGNANT_USERNAME="enseignant001"
ENSEIGNANT_PASSWORD="password123"

# UUIDs (à remplacer après création)
ADMIN_PROFIL_ID=""
ETUDIANT_PROFIL_ID=""
ENSEIGNANT_PROFIL_ID=""
ROLE_ETUDIANT_ID=""
ROLE_ENSEIGNANT_ID=""
GROUPE_L1_INFO_ID=""
PERMISSION_INSCRIPTION_ID=""
```

### Variables Stockées Pendant les Tests
```bash
# Tokens (à stocker après login)
ADMIN_ACCESS_TOKEN=""
ETUDIANT_ACCESS_TOKEN=""
ENSEIGNANT_ACCESS_TOKEN=""

# IDs créés pendant les tests
SOURCE_SCOLARITE_ID=""
SOURCE_NOTES_ID=""
PERMISSION_SCOLARITE_INSCRIPTION_ID=""
PERMISSION_NOTES_CONSULTATION_ID=""
CLASSE_L1_INFO_GROUPE_ID=""
```

---

## Scénarios de Test Complet

### Phase 1: Initialisation et Authentification

#### 1.1 Test Login Admin
```bash
curl -X POST "${IAM_BASE_URL}/tokens/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "'${ADMIN_USERNAME}'",
    "password": "'${ADMIN_PASSWORD}'"
  }'
```

**Stockez le access_token dans ADMIN_ACCESS_TOKEN**

#### 1.2 Test Login Étudiant
```bash
curl -X POST "${IAM_BASE_URL}/tokens/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "'${ETUDIANT_USERNAME}'",
    "password": "'${ETUDIANT_PASSWORD}'"
  }'
```

**Stockez le access_token dans ETUDIANT_ACCESS_TOKEN**

#### 1.3 Valider Token
```bash
curl -X POST "${IAM_BASE_URL}/tokens/validate" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "'${ADMIN_ACCESS_TOKEN}'",
    "token_type": "access"
  }'
```

### Phase 2: Permissions

#### 2.1 Créer Source Scolarité
```bash
curl -X POST "${IAM_BASE_URL}/permissions/sources" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "scolarite",
    "nom": "Module Scolarité",
    "description": "Gestion de la scolarité",
    "version": "1.0.0",
    "url_base": "http://localhost:8001"
  }'
```

**Stockez l'ID dans SOURCE_SCOLARITE_ID**

#### 2.2 Enregistrer Permissions Scolarité
```bash
curl -X POST "${IAM_BASE_URL}/permissions/enregistrer" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "source_code": "scolarite",
    "source_nom": "Module Scolarité",
    "source_version": "1.0.0",
    "source_url": "http://localhost:8001",
    "permissions": [
      {
        "code": "scolarite.inscription.creer",
        "nom": "Créer une inscription",
        "description": "Permet de créer une nouvelle inscription",
        "domaine": "scolarite",
        "ressource": "inscription",
        "action": "creer",
        "niveau_risque": "MOYEN"
      },
      {
        "code": "scolarite.inscription.consulter",
        "nom": "Consulter les inscriptions",
        "description": "Permet de consulter les inscriptions",
        "domaine": "scolarite",
        "ressource": "inscription",
        "action": "consulter",
        "niveau_risque": "FAIBLE"
      },
      {
        "code": "scolarite.inscription.modifier",
        "nom": "Modifier une inscription",
        "description": "Permet de modifier une inscription",
        "domaine": "scolarite",
        "ressource": "inscription",
        "action": "modifier",
        "niveau_risque": "MOYEN"
      },
      {
        "code": "scolarite.inscription.supprimer",
        "nom": "Supprimer une inscription",
        "description": "Permet de supprimer une inscription",
        "domaine": "scolarite",
        "ressource": "inscription",
        "action": "supprimer",
        "niveau_risque": "ELEVE"
      }
    ]
  }'
```

#### 2.3 Lister Permissions
```bash
curl -X GET "${IAM_BASE_URL}/permissions?domaine=scolarite&skip=0&limit=100" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 2.4 Détail Permission
```bash
curl -X GET "${IAM_BASE_URL}/permissions/{permission_id}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

### Phase 3: Rôles

#### 3.1 Créer Rôle Étudiant
```bash
curl -X POST "${IAM_BASE_URL}/roles/" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "etudiant",
    "nom": "Étudiant",
    "description": "Rôle de base pour les étudiants",
    "type_role": "FONCTIONNEL",
    "perimetre_obligatoire": false,
    "permissions_ids": []
  }'
```

**Stockez l'ID dans ROLE_ETUDIANT_ID**

#### 3.2 Créer Rôle Enseignant
```bash
curl -X POST "${IAM_BASE_URL}/roles/" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "enseignant",
    "nom": "Enseignant",
    "description": "Rôle pour les enseignants",
    "type_role": "FONCTIONNEL",
    "perimetre_obligatoire": false,
    "permissions_ids": []
  }'
```

**Stockez l'ID dans ROLE_ENSEIGNANT_ID**

#### 3.3 Ajouter Permissions au Rôle Étudiant
```bash
curl -X POST "${IAM_BASE_URL}/roles/${ROLE_ETUDIANT_ID}/permissions/ajouter" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permissions_ids": ["{permission_scolarite_inscription_consulter_id}"],
    "raison": "Permissions de base pour étudiants"
  }'
```

#### 3.4 Ajouter Permissions au Rôle Enseignant
```bash
curl -X POST "${IAM_BASE_URL}/roles/${ROLE_ENSEIGNANT_ID}/permissions/ajouter" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permissions_ids": [
      "{permission_scolarite_inscription_creer_id}",
      "{permission_scolarite_inscription_consulter_id}",
      "{permission_scolarite_inscription_modifier_id}"
    ],
    "raison": "Permissions complètes pour enseignants"
  }'
```

#### 3.5 Lister Rôles
```bash
curl -X GET "${IAM_BASE_URL}/roles?skip=0&limit=50" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 3.6 Détail Rôle
```bash
curl -X GET "${IAM_BASE_URL}/roles/${ROLE_ETUDIANT_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

### Phase 4: Profils

#### 4.1 Créer Profil Étudiant avec Credentials
```bash
curl -X POST "${IAM_BASE_URL}/profils/" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "nom": "Dupont",
    "prenom": "Jean",
    "email": "jean.dupont@example.com",
    "telephone": "+33612345678",
    "identifiant_national": "ETU001",
    "type_profil": "ETUDIANT",
    "username": "jean.dupont",
    "password": "password123!",
    "require_password_change": false,
    "classe": "L1",
    "niveau": "Licence 1",
    "specialite": "Informatique",
    "annee_scolaire": "2024-2025"
  }'
```

**Stockez l'ID dans ETUDIANT_PROFIL_ID**

#### 4.2 Créer Profil Enseignant avec Credentials
```bash
curl -X POST "${IAM_BASE_URL}/profils/" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "nom": "Durand",
    "prenom": "Marie",
    "email": "marie.durand@example.com",
    "telephone": "+33687654321",
    "identifiant_national": "ENS001",
    "type_profil": "ENSEIGNANT",
    "username": "marie.durand",
    "password": "password123!",
    "require_password_change": false,
    "specialite": "Informatique"
  }'
```

**Stockez l'ID dans ENSEIGNANT_PROFIL_ID**

#### 4.3 Lister Profils
```bash
curl -X GET "${IAM_BASE_URL}/profils?skip=0&limit=50" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 4.4 Détail Profil
```bash
curl -X GET "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 4.5 Assigner Rôle Étudiant
```bash
curl -X POST "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "'${ROLE_ETUDIANT_ID}'",
    "perimetre": {"classe": "L1"},
    "raison": "Assignation rôle étudiant de base"
  }'
```

#### 4.6 Assigner Rôle Enseignant
```bash
curl -X POST "${IAM_BASE_URL}/profils/${ENSEIGNANT_PROFIL_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "'${ROLE_ENSEIGNANT_ID}'",
    "perimetre": {"specialite": "Informatique"},
    "raison": "Assignation rôle enseignant"
  }'
```

#### 4.7 Lister Rôles du Profil
```bash
curl -X GET "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 4.8 Modifier Profil
```bash
curl -X PUT "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jean.dupont.updated@example.com",
    "telephone": "+33612345679",
    "notes": "Profil mis à jour pour test"
  }'
```

### Phase 5: Groupes

#### 5.1 Créer Groupe Classe L1 Info
```bash
curl -X POST "${IAM_BASE_URL}/groupes/" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "classe_L1_info",
    "nom": "Classe L1 Informatique",
    "description": "Groupe pour les étudiants de L1 info",
    "type_groupe": "FONCTIONNEL",
    "perimetre": {"classe": "L1", "specialite": "informatique"},
    "roles_ids": ["'${ROLE_ETUDIANT_ID}'"]
  }'
```

**Stockez l'ID dans GROUPE_L1_INFO_ID**

#### 5.2 Lister Groupes
```bash
curl -X GET "${IAM_BASE_URL}/groupes?skip=0&limit=50" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 5.3 Détail Groupe
```bash
curl -X GET "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 5.4 Ajouter Membre au Groupe
```bash
curl -X POST "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}/membres" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "profil_id": "'${ETUDIANT_PROFIL_ID}'",
    "perimetre": {"classe": "L1"},
    "raison": "Inscription dans la classe L1 info"
  }'
```

#### 5.5 Modifier Groupe
```bash
curl -X PUT "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Groupe mis à jour pour les étudiants de L1 info 2024-2025",
    "notes": "Ajout de l'année scolaire"
  }'
```

### Phase 6: Habilitations

#### 6.1 Vérifier Habilitations Étudiant
```bash
curl -X GET "${IAM_BASE_URL}/habilitations/moi" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}"
```

#### 6.2 Vérifier Habilitations Enseignant
```bash
curl -X GET "${IAM_BASE_URL}/habilitations/moi" \
  -H "Authorization: Bearer ${ENSEIGNANT_ACCESS_TOKEN}"
```

#### 6.3 Vérifier Permission Spécifique
```bash
curl -X POST "${IAM_BASE_URL}/habilitations/verifier" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permission_code": "scolarite.inscription.consulter",
    "perimetre": {"classe": "L1"},
    "contexte": {"module": "scolarite"}
  }'
```

#### 6.4 Vérifier Permission Non Autorisée
```bash
curl -X POST "${IAM_BASE_URL}/habilitations/verifier" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permission_code": "scolarite.inscription.supprimer",
    "perimetre": {"classe": "L1"},
    "contexte": {"module": "scolarite"}
  }'
```

### Phase 7: Gateway

#### 7.1 Lister Modules Disponibles
```bash
curl -X GET "${IAM_BASE_URL}/gateway/modules" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 7.2 Test Forward vers Module Scolarité (Enseignant)
```bash
curl -X POST "${IAM_BASE_URL}/gateway/forward" \
  -H "Authorization: Bearer ${ENSEIGNANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "module": "scolarite",
    "path": "/api/v1/inscriptions",
    "method": "POST",
    "body": {
      "etudiant_id": "'${ETUDIANT_PROFIL_ID}'",
      "classe": "L1",
      "specialite": "informatique"
    }
  }'
```

#### 7.3 Test Forward Consultation (Étudiant)
```bash
curl -X POST "${IAM_BASE_URL}/gateway/forward" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "module": "scolarite",
    "path": "/api/v1/inscriptions",
    "method": "GET",
    "params": {
      "classe": "L1"
    }
  }'
```

#### 7.4 Test Forward Non Autorisé
```bash
curl -X POST "${IAM_BASE_URL}/gateway/forward" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "module": "scolarite",
    "path": "/api/v1/inscriptions",
    "method": "DELETE",
    "body": {
      "inscription_id": "test-id"
    }
  }'
```

### Phase 8: Audit

#### 8.1 Consulter Mon Journal (Étudiant)
```bash
curl -X GET "${IAM_BASE_URL}/audit/moi?skip=0&limit=50" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}"
```

#### 8.2 Journal Global (Admin)
```bash
curl -X GET "${IAM_BASE_URL}/audit?skip=0&limit=100" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 8.3 Journal par Profil
```bash
curl -X GET "${IAM_BASE_URL}/audit/profil/${ETUDIANT_PROFIL_ID}?skip=0&limit=50" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

### Phase 9: Configuration Tokens

#### 9.1 Créer Configuration Token
```bash
curl -X POST "${IAM_BASE_URL}/token-config/" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "access_token_lifetime": 7200,
    "refresh_token_lifetime": 172800,
    "issuer": "iam-local-test",
    "algorithm": "HS256",
    "require_password_change_days": 90,
    "max_sessions_per_user": 3,
    "session_timeout": 7200
  }'
```

#### 9.2 Lister Configurations
```bash
curl -X GET "${IAM_BASE_URL}/token-config/?skip=0&limit=10" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 9.3 Configuration Active
```bash
curl -X GET "${IAM_BASE_URL}/token-config/active" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

### Phase 10: Tests de Modification et Suppression

#### 10.1 Modifier Rôle
```bash
curl -X PUT "${IAM_BASE_URL}/roles/${ROLE_ETUDIANT_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Rôle étudiant mis à jour avec permissions étendues",
    "notes": "Mise à jour après tests"
  }'
```

#### 10.2 Retirer Permission du Rôle
```bash
curl -X POST "${IAM_BASE_URL}/roles/${ROLE_ETUDIANT_ID}/permissions/retirer" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permissions_ids": ["{permission_to_remove_id}"],
    "raison": "Retrait pour test"
  }'
```

#### 10.3 Retirer Membre du Groupe
```bash
curl -X DELETE "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}/membres/{assignation_id}?raison=Test suppression" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 10.4 Révoquer Rôle du Profil
```bash
curl -X DELETE "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/roles/{assignation_id}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "raison": "Test révocation"
  }'
```

#### 10.5 Suspendre Profil
```bash
curl -X POST "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/suspendre" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "raison": "Test suspension"
  }'
```

#### 10.6 Réactiver Profil
```bash
curl -X POST "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/reactiver" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 10.7 Supprimer Groupe
```bash
curl -X DELETE "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 10.8 Supprimer Rôle
```bash
curl -X DELETE "${IAM_BASE_URL}/roles/${ROLE_ETUDIANT_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

#### 10.9 Supprimer Profil (Soft Delete)
```bash
curl -X DELETE "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

### Phase 11: Nettoyage Final

#### 11.1 Logout
```bash
curl -X POST "${IAM_BASE_URL}/tokens/logout" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"

curl -X POST "${IAM_BASE_URL}/tokens/logout" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}"

curl -X POST "${IAM_BASE_URL}/tokens/logout" \
  -H "Authorization: Bearer ${ENSEIGNANT_ACCESS_TOKEN}"
```

#### 11.2 Révoquer Sessions
```bash
curl -X DELETE "${IAM_BASE_URL}/tokens/sessions/{session_id}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

---

## Notes Importantes

1. **Ordre des Tests** : Suivez l'ordre logique des phases pour garantir que les dépendances sont créées avant d'être utilisées.

2. **Variables** : Remplacez les placeholders `{uuid}` par les vrais IDs retournés par les API.

3. **Permissions** : Certains tests nécessitent des permissions spécifiques. Assurez-vous que l'utilisateur admin a les permissions requises.

4. **Gateway** : Les tests de gateway nécessitent que les modules métier soient en cours d'exécution.

5. **Base de Données** : Ces tests partent d'une base de données vide. Si des données existent déjà, adaptez les tests.

6. **Tokens** : Les tokens ont une durée de vie limitée. Rafraîchissez-les si nécessaire pendant les tests.

7. **Audit** : Toutes les actions sont tracées dans le journal d'audit pour vérification.

---

## Conclusion

Cette documentation couvre l'ensemble des API du microservice IAM Local avec des scénarios de test complets. Les tests suivent une progression logique :

1. **GET** : Validation des données existantes (initialement vide)
2. **POST** : Création des données de test
3. **PATCH/PUT** : Modification des données créées
4. **GET** : Vérification des modifications
5. **DELETE** : Suppression et nettoyage

Cette approche garantit une couverture complète des fonctionnalités tout en maintenant un état cohérent de la base de données.
