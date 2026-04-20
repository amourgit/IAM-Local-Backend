#!/usr/bin/env bash
# ================================================================
# IAM LOCAL — GUIDE COMPLET DES REQUÊTES CURL
# G20® National · Backend: FastAPI · Préfixe: /api/v1
# ================================================================
# Usage: bash ce_fichier.sh  (ou copiez les commandes une par une)
# Les variables $ACCESS_TOKEN, $PROFIL_ID, etc. se peuplent
# automatiquement au fur et à mesure — exécutez dans l'ordre.
# ================================================================

BASE_URL="http://localhost:8002/api/v1"

# ================================================================
# MODULE 01 — AUTHENTIFICATION & TOKENS
# Dépendances : aucune (point d'entrée)
# ================================================================

# ── [01.1] LOGIN — Obtenir access_token + refresh_token ────────
# POST /tokens/login
# Réponse: access_token, refresh_token, session_id, user
curl -s -X POST "$BASE_URL/tokens/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "bootstrap",
    "password": "BootstrapTemp@2024!"
  }' | tee /tmp/login_response.json | python3 -m json.tool

# → Extraire les tokens pour les requêtes suivantes
export ACCESS_TOKEN=$(cat /tmp/login_response.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['access_token'])")
export REFRESH_TOKEN=$(cat /tmp/login_response.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['refresh_token'])")
export SESSION_ID=$(cat /tmp/login_response.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))")
export MON_PROFIL_ID=$(cat /tmp/login_response.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('user',{}).get('id',''))")

echo ""
echo "✅ ACCESS_TOKEN  = ${ACCESS_TOKEN:0:40}..."
echo "✅ REFRESH_TOKEN = ${REFRESH_TOKEN:0:40}..."
echo "✅ SESSION_ID    = $SESSION_ID"
echo "✅ MON_PROFIL_ID = $MON_PROFIL_ID"


# ── [01.2] REFRESH — Renouveler l'access_token ─────────────────
# POST /tokens/refresh
curl -s -X POST "$BASE_URL/tokens/refresh" \
  -H "Content-Type: application/json" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN\"
  }" | tee /tmp/refresh_response.json | python3 -m json.tool

export ACCESS_TOKEN=$(cat /tmp/refresh_response.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['access_token'])")
echo "✅ Nouveau ACCESS_TOKEN = ${ACCESS_TOKEN:0:40}..."


# ── [01.3] VALIDER un token ─────────────────────────────────────
# POST /tokens/validate
curl -s -X POST "$BASE_URL/tokens/validate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"token\": \"$ACCESS_TOKEN\"
  }" | python3 -m json.tool


# ── [01.4] CHANGER son mot de passe ────────────────────────────
# POST /tokens/change-password
curl -s -X POST "$BASE_URL/tokens/change-password" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "old_password": "BootstrapTemp@2024!",
    "new_password": "NouveauMDP456@",
    "confirm_password": "NouveauMDP456@"
  }' | python3 -m json.tool


# ── [01.5] LISTER ses sessions actives ─────────────────────────
# GET /tokens/sessions
curl -s -X GET "$BASE_URL/tokens/sessions" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/sessions_response.json | python3 -m json.tool

export SESSION_ID_CIBLE=$(cat /tmp/sessions_response.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
sessions = d.get('sessions', [])
# Prendre la première session qui n'est pas la session courante
for s in sessions:
    if s.get('id') != '$SESSION_ID':
        print(s['id'])
        break
" 2>/dev/null || echo "")
echo "Session cible pour révocation: $SESSION_ID_CIBLE"


# ── [01.6] RÉVOQUER une session spécifique ─────────────────────
# DELETE /tokens/sessions/{session_id}
# (Utiliser $SESSION_ID_CIBLE si disponible, sinon la session courante)
# ATTENTION: révoquer la session courante vous déconnecte
curl -s -X DELETE "$BASE_URL/tokens/sessions/${SESSION_ID_CIBLE:-$SESSION_ID}" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [01.7] STATS des sessions (admin) ──────────────────────────
# GET /tokens/sessions/stats
curl -s -X GET "$BASE_URL/tokens/sessions/stats" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [01.8] MÉTRIQUES des tokens (admin) ────────────────────────
# GET /tokens/metrics
curl -s -X GET "$BASE_URL/tokens/metrics" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [01.9] STATUT SYNC IAM Central ─────────────────────────────
# GET /tokens/sync/status
curl -s -X GET "$BASE_URL/tokens/sync/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [01.10] LOGOUT — Révoquer la session courante ──────────────
# POST /tokens/logout
# ⚠️  À exécuter en DERNIER dans ce bloc (invalide le token)
# curl -s -X POST "$BASE_URL/tokens/logout" \
#   -H "Authorization: Bearer $ACCESS_TOKEN" \
#   | python3 -m json.tool


# ================================================================
# MODULE 02 — CONFIGURATION DES TOKENS (token_config)
# Dépendances : ACCESS_TOKEN admin
# ================================================================

# ── [02.1] LISTER les configurations de tokens ─────────────────
# GET /token-config/
curl -s -X GET "$BASE_URL/token-config/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/token_configs.json | python3 -m json.tool

export TOKEN_CONFIG_ID=$(cat /tmp/token_configs.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
configs = d if isinstance(d, list) else d.get('items', [d])
if configs: print(configs[0]['id'])
" 2>/dev/null || echo "")
echo "✅ TOKEN_CONFIG_ID = $TOKEN_CONFIG_ID"


# ── [02.2] DÉTAIL d'une configuration ──────────────────────────
# GET /token-config/{id}
curl -s -X GET "$BASE_URL/token-config/$TOKEN_CONFIG_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [02.3] CRÉER une configuration ─────────────────────────────
# POST /token-config/
curl -s -X POST "$BASE_URL/token-config/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "nom": "Config Standard",
    "type_token": "access",
    "duree_validite_minutes": 60,
    "actif": true,
    "description": "Configuration standard pour les tokens d'\''accès"
  }' | tee /tmp/new_token_config.json | python3 -m json.tool

export NEW_TOKEN_CONFIG_ID=$(cat /tmp/new_token_config.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")


# ── [02.4] MODIFIER une configuration ──────────────────────────
# PUT /token-config/{id}
curl -s -X PUT "$BASE_URL/token-config/$NEW_TOKEN_CONFIG_ID" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "duree_validite_minutes": 120,
    "description": "Configuration standard mise à jour — 2h"
  }' | python3 -m json.tool


# ── [02.5] ACTIVER/DÉSACTIVER une configuration ────────────────
# POST /token-config/{id}/activer
curl -s -X POST "$BASE_URL/token-config/$NEW_TOKEN_CONFIG_ID/activer" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ================================================================
# MODULE 03 — PROFILS (Gestion des utilisateurs)
# Dépendances : ACCESS_TOKEN
# Ordre: créer → lire → modifier → suspendre → réactiver → rôles → supprimer
# ================================================================

# ── [03.1] LISTER tous les profils ─────────────────────────────
# GET /profils/?type_profil=&statut=&q=&skip=0&limit=50
curl -s -X GET "$BASE_URL/profils/?skip=0&limit=50" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/profils_list.json | python3 -m json.tool

export PREMIER_PROFIL_ID=$(cat /tmp/profils_list.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('items', [])
if items: print(items[0]['id'])
" 2>/dev/null || echo "")
echo "✅ PREMIER_PROFIL_ID = $PREMIER_PROFIL_ID"


# ── [03.2] FILTRER — Par type ───────────────────────────────────
# GET /profils/?type_profil=admin
curl -s -X GET "$BASE_URL/profils/?type_profil=admin&limit=20" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [03.3] FILTRER — Par statut ────────────────────────────────
# GET /profils/?statut=actif
curl -s -X GET "$BASE_URL/profils/?statut=actif&limit=20" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [03.4] RECHERCHE — Par nom/username/email ──────────────────
# GET /profils/?q=dupont
curl -s -X GET "$BASE_URL/profils/?q=admin&limit=10" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [03.5] CRÉER un profil avec credentials locales ────────────
# POST /profils/
curl -s -X POST "$BASE_URL/profils/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "nom": "Dupont",
    "prenom": "Jean",
    "email": "jean.dupont@education.ga",
    "telephone": "+241 01 23 45 67",
    "identifiant_national": "ELEVE-2024-0001",
    "type_profil": "etudiant",
    "username": "jean.dupont",
    "password": "TempPass123!",
    "require_password_change": true,
    "classe": "Terminale C",
    "niveau": "Lycée",
    "specialite": "Mathématiques",
    "annee_scolaire": "2024-2025",
    "notes": "Élève transféré de l'\''établissement B"
  }' | tee /tmp/new_profil.json | python3 -m json.tool

export PROFIL_ID=$(cat /tmp/new_profil.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "✅ PROFIL_ID = $PROFIL_ID"


# ── [03.6] CRÉER un profil sans credentials (liaison IAM Central)
# POST /profils/sans-credentials
curl -s -X POST "$BASE_URL/profils/sans-credentials" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "nom": "Martin",
    "prenom": "Sophie",
    "email": "sophie.martin@education.ga",
    "identifiant_national": "PERS-2024-0042",
    "type_profil": "enseignant",
    "notes": "Enseignante principale — classe de 5ème"
  }' | tee /tmp/new_profil_sans_cred.json | python3 -m json.tool

export PROFIL_SANS_CRED_ID=$(cat /tmp/new_profil_sans_cred.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "✅ PROFIL_SANS_CRED_ID = $PROFIL_SANS_CRED_ID"


# ── [03.7] DÉTAIL d'un profil ──────────────────────────────────
# GET /profils/{id}
curl -s -X GET "$BASE_URL/profils/$PROFIL_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [03.8] MON PROFIL (profil de l'utilisateur connecté) ───────
# GET /profils/moi
curl -s -X GET "$BASE_URL/profils/moi" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [03.9] MODIFIER un profil ──────────────────────────────────
# PUT /profils/{id}
curl -s -X PUT "$BASE_URL/profils/$PROFIL_ID" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "nom": "Dupont-Moreau",
    "email": "jean.dupont.moreau@education.ga",
    "telephone": "+241 01 23 45 99",
    "notes": "Nom mis à jour suite au mariage des parents"
  }' | python3 -m json.tool


# ── [03.10] SUSPENDRE un profil ────────────────────────────────
# POST /profils/{id}/suspendre
curl -s -X POST "$BASE_URL/profils/$PROFIL_ID/suspendre" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "raison": "Violation du règlement intérieur — accès non autorisé à des ressources sensibles"
  }' | python3 -m json.tool


# ── [03.11] RÉACTIVER un profil ────────────────────────────────
# POST /profils/{id}/reactiver
curl -s -X POST "$BASE_URL/profils/$PROFIL_ID/reactiver" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{}' | python3 -m json.tool


# ── [03.12] ASSIGNER un rôle à un profil ───────────────────────
# POST /profils/{id}/roles
# (nécessite ROLE_ID — voir Module 04)
curl -s -X POST "$BASE_URL/profils/$PROFIL_ID/roles" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"profil_id\": \"$PROFIL_ID\",
    \"role_id\": \"$ROLE_ID\",
    \"date_fin\": \"2025-08-31T23:59:59\",
    \"raison\": \"Assignation pour l'année scolaire 2024-2025\"
  }" | tee /tmp/assignation.json | python3 -m json.tool

export ASSIGNATION_ID=$(cat /tmp/assignation.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "✅ ASSIGNATION_ID = $ASSIGNATION_ID"


# ── [03.13] LISTER les rôles d'un profil ───────────────────────
# GET /profils/{id}/roles
curl -s -X GET "$BASE_URL/profils/$PROFIL_ID/roles" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [03.14] RÉVOQUER un rôle d'un profil ───────────────────────
# DELETE /profils/{id}/roles/{assignation_id}
curl -s -X DELETE "$BASE_URL/profils/$PROFIL_ID/roles/$ASSIGNATION_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [03.15] SUPPRIMER un profil (soft delete) ──────────────────
# DELETE /profils/{id}
# ⚠️  Action irréversible — le profil passe en statut 'supprime'
curl -s -X DELETE "$BASE_URL/profils/$PROFIL_SANS_CRED_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ================================================================
# MODULE 04 — RÔLES
# Dépendances : ACCESS_TOKEN
# Ordre: créer → lire → modifier → permissions → supprimer
# ================================================================

# ── [04.1] LISTER tous les rôles ───────────────────────────────
# GET /roles/?type_role=&q=&skip=0&limit=200
curl -s -X GET "$BASE_URL/roles/?skip=0&limit=200" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/roles_list.json | python3 -m json.tool

export ROLE_ID=$(cat /tmp/roles_list.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('items', [])
if items: print(items[0]['id'])
" 2>/dev/null || echo "")
echo "✅ ROLE_ID = $ROLE_ID"


# ── [04.2] FILTRER — Par type de rôle ──────────────────────────
# GET /roles/?type_role=fonctionnel
curl -s -X GET "$BASE_URL/roles/?type_role=fonctionnel&limit=50" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [04.3] RECHERCHE par nom ou code ───────────────────────────
# GET /roles/?q=admin
curl -s -X GET "$BASE_URL/roles/?q=admin" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [04.4] CRÉER un rôle ───────────────────────────────────────
# POST /roles/
curl -s -X POST "$BASE_URL/roles/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "code": "gestionnaire.profils",
    "nom": "Gestionnaire des profils",
    "description": "Accès complet à la gestion des profils utilisateurs — création, modification, suspension",
    "type_role": "fonctionnel"
  }' | tee /tmp/new_role.json | python3 -m json.tool

export NEW_ROLE_ID=$(cat /tmp/new_role.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "✅ NEW_ROLE_ID = $NEW_ROLE_ID"


# ── [04.5] DÉTAIL d'un rôle ────────────────────────────────────
# GET /roles/{id}
curl -s -X GET "$BASE_URL/roles/$NEW_ROLE_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [04.6] MODIFIER un rôle ────────────────────────────────────
# PUT /roles/{id}
curl -s -X PUT "$BASE_URL/roles/$NEW_ROLE_ID" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "nom": "Gestionnaire des profils (étendu)",
    "description": "Accès complet à la gestion des profils + consultation des habilitations",
    "type_role": "fonctionnel"
  }' | python3 -m json.tool


# ── [04.7] AJOUTER des permissions à un rôle ───────────────────
# POST /roles/{id}/permissions/ajouter
# (nécessite PERMISSION_ID — voir Module 05)
curl -s -X POST "$BASE_URL/roles/$NEW_ROLE_ID/permissions/ajouter" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"permission_ids\": [\"$PERMISSION_ID\", \"$PERMISSION_ID_2\"]
  }" | python3 -m json.tool


# ── [04.8] RETIRER des permissions d'un rôle ───────────────────
# POST /roles/{id}/permissions/retirer
curl -s -X POST "$BASE_URL/roles/$NEW_ROLE_ID/permissions/retirer" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"permission_ids\": [\"$PERMISSION_ID_2\"]
  }" | python3 -m json.tool


# ── [04.9] SUPPRIMER un rôle ───────────────────────────────────
# DELETE /roles/{id}
# ⚠️  Impossible si des profils ont ce rôle actif
curl -s -X DELETE "$BASE_URL/roles/$NEW_ROLE_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ================================================================
# MODULE 05 — PERMISSIONS
# Dépendances : ACCESS_TOKEN
# Ordre: sources → créer → lire → modifier
# ================================================================

# ── [05.1] LISTER les sources (microservices) ──────────────────
# GET /permissions/sources
curl -s -X GET "$BASE_URL/permissions/sources" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/sources_list.json | python3 -m json.tool

export SOURCE_ID=$(cat /tmp/sources_list.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('items', [])
if items: print(items[0]['id'])
" 2>/dev/null || echo "")
export SOURCE_CODE=$(cat /tmp/sources_list.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('items', [])
if items: print(items[0].get('code',''))
" 2>/dev/null || echo "")
echo "✅ SOURCE_ID   = $SOURCE_ID"
echo "✅ SOURCE_CODE = $SOURCE_CODE"


# ── [05.2] ENREGISTRER une source (microservice) ───────────────
# POST /permissions/sources
curl -s -X POST "$BASE_URL/permissions/sources" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "code": "iam-local",
    "nom": "IAM Local",
    "description": "Système de gestion des identités et des accès — déploiement local G20®",
    "url": "http://localhost:8000"
  }' | tee /tmp/new_source.json | python3 -m json.tool

export NEW_SOURCE_ID=$(cat /tmp/new_source.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "✅ NEW_SOURCE_ID = $NEW_SOURCE_ID"


# ── [05.3] ENREGISTRER des permissions en masse (microservice) ─
# POST /permissions/enregistrer
curl -s -X POST "$BASE_URL/permissions/enregistrer" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "source_code": "iam-local",
    "source_nom": "IAM Local",
    "permissions": [
      {
        "code": "iam.profil.lire",
        "nom": "Consulter les profils",
        "domaine": "iam",
        "ressource": "profil",
        "action": "lire"
      },
      {
        "code": "iam.profil.creer",
        "nom": "Créer un profil",
        "domaine": "iam",
        "ressource": "profil",
        "action": "creer"
      },
      {
        "code": "iam.profil.modifier",
        "nom": "Modifier un profil",
        "domaine": "iam",
        "ressource": "profil",
        "action": "modifier"
      },
      {
        "code": "iam.profil.supprimer",
        "nom": "Supprimer un profil",
        "domaine": "iam",
        "ressource": "profil",
        "action": "supprimer"
      },
      {
        "code": "iam.profil.suspendre",
        "nom": "Suspendre/réactiver un profil",
        "domaine": "iam",
        "ressource": "profil",
        "action": "suspendre"
      },
      {
        "code": "iam.role.lire",
        "nom": "Consulter les rôles",
        "domaine": "iam",
        "ressource": "role",
        "action": "lire"
      },
      {
        "code": "iam.role.creer",
        "nom": "Créer un rôle",
        "domaine": "iam",
        "ressource": "role",
        "action": "creer"
      },
      {
        "code": "iam.role.modifier",
        "nom": "Modifier un rôle",
        "domaine": "iam",
        "ressource": "role",
        "action": "modifier"
      },
      {
        "code": "iam.role.supprimer",
        "nom": "Supprimer un rôle",
        "domaine": "iam",
        "ressource": "role",
        "action": "supprimer"
      },
      {
        "code": "iam.permission.lire",
        "nom": "Consulter les permissions",
        "domaine": "iam",
        "ressource": "permission",
        "action": "lire"
      },
      {
        "code": "iam.permission.creer",
        "nom": "Créer une permission",
        "domaine": "iam",
        "ressource": "permission",
        "action": "creer"
      },
      {
        "code": "iam.permission.modifier",
        "nom": "Modifier une permission",
        "domaine": "iam",
        "ressource": "permission",
        "action": "modifier"
      },
      {
        "code": "iam.groupe.lire",
        "nom": "Consulter les groupes",
        "domaine": "iam",
        "ressource": "groupe",
        "action": "lire"
      },
      {
        "code": "iam.groupe.creer",
        "nom": "Créer un groupe",
        "domaine": "iam",
        "ressource": "groupe",
        "action": "creer"
      },
      {
        "code": "iam.groupe.modifier",
        "nom": "Modifier un groupe",
        "domaine": "iam",
        "ressource": "groupe",
        "action": "modifier"
      },
      {
        "code": "iam.audit.lire",
        "nom": "Consulter les journaux d'\''audit",
        "domaine": "audit",
        "ressource": "journal",
        "action": "lire"
      },
      {
        "code": "iam.admin.all",
        "nom": "Accès administrateur complet",
        "domaine": "admin",
        "ressource": "*",
        "action": "admin"
      }
    ]
  }' | python3 -m json.tool


# ── [05.4] LISTER toutes les permissions ───────────────────────
# GET /permissions/?domaine=&q=&skip=0&limit=500
curl -s -X GET "$BASE_URL/permissions/?skip=0&limit=500" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/permissions_list.json | python3 -m json.tool

export PERMISSION_ID=$(cat /tmp/permissions_list.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('items', [])
if items: print(items[0]['id'])
" 2>/dev/null || echo "")
export PERMISSION_ID_2=$(cat /tmp/permissions_list.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('items', [])
if len(items) > 1: print(items[1]['id'])
" 2>/dev/null || echo "")
echo "✅ PERMISSION_ID   = $PERMISSION_ID"
echo "✅ PERMISSION_ID_2 = $PERMISSION_ID_2"


# ── [05.5] FILTRER — Par domaine ───────────────────────────────
# GET /permissions/?domaine=iam
curl -s -X GET "$BASE_URL/permissions/?domaine=iam&limit=100" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [05.6] RECHERCHE par code ou nom ───────────────────────────
# GET /permissions/?q=profil
curl -s -X GET "$BASE_URL/permissions/?q=profil&limit=20" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [05.7] CRÉER une permission manuelle ───────────────────────
# POST /permissions/
curl -s -X POST "$BASE_URL/permissions/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "code": "rapport.statistiques.lire",
    "nom": "Consulter les statistiques",
    "domaine": "rapport",
    "ressource": "statistiques",
    "action": "lire",
    "description": "Accès en lecture aux tableaux de bord et statistiques de l'\''établissement"
  }' | tee /tmp/new_permission.json | python3 -m json.tool

export NEW_PERMISSION_ID=$(cat /tmp/new_permission.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "✅ NEW_PERMISSION_ID = $NEW_PERMISSION_ID"


# ── [05.8] CRÉER une permission custom ─────────────────────────
# POST /permissions/custom
curl -s -X POST "$BASE_URL/permissions/custom" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "code": "custom.rapport.exporter",
    "nom": "Exporter les rapports (custom)",
    "domaine": "rapport",
    "description": "Permission personnalisée — export PDF/Excel des rapports de direction"
  }' | tee /tmp/custom_permission.json | python3 -m json.tool

export CUSTOM_PERM_ID=$(cat /tmp/custom_permission.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "✅ CUSTOM_PERM_ID = $CUSTOM_PERM_ID"


# ── [05.9] DÉTAIL d'une permission ─────────────────────────────
# GET /permissions/{id}
curl -s -X GET "$BASE_URL/permissions/$NEW_PERMISSION_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [05.10] MODIFIER une permission ────────────────────────────
# PUT /permissions/{id}
curl -s -X PUT "$BASE_URL/permissions/$NEW_PERMISSION_ID" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "nom": "Consulter les statistiques établissement",
    "description": "Lecture des statistiques — tableaux de bord direction et administration"
  }' | python3 -m json.tool


# ================================================================
# MODULE 06 — HABILITATIONS
# Dépendances : ACCESS_TOKEN, PROFIL_ID
# Lecture seule — agrège rôles + permissions par profil
# ================================================================

# ── [06.1] MES HABILITATIONS (profil connecté) ─────────────────
# GET /habilitations/moi
curl -s -X GET "$BASE_URL/habilitations/moi" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [06.2] HABILITATIONS d'un profil spécifique ────────────────
# GET /habilitations/{profil_id}
curl -s -X GET "$BASE_URL/habilitations/$PROFIL_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [06.3] VÉRIFIER une permission spécifique ──────────────────
# GET /habilitations/{profil_id}/verifier?permission_code=iam.profil.lire
curl -s -X GET "$BASE_URL/habilitations/$PROFIL_ID/verifier?permission_code=iam.profil.lire" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [06.4] HABILITATIONS — Vue globale (admin) ─────────────────
# GET /habilitations/ (liste de tous les profils avec leurs habilitations résumées)
curl -s -X GET "$BASE_URL/habilitations/?skip=0&limit=20" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ================================================================
# MODULE 07 — GROUPES
# Dépendances : ACCESS_TOKEN, PROFIL_ID
# Ordre: créer → lire → membres → permissions → supprimer
# ================================================================

# ── [07.1] LISTER tous les groupes ─────────────────────────────
# GET /groupes/?skip=0&limit=100
curl -s -X GET "$BASE_URL/groupes/?skip=0&limit=100" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/groupes_list.json | python3 -m json.tool

export GROUPE_ID=$(cat /tmp/groupes_list.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d if isinstance(d, list) else d.get('items', [])
if items: print(items[0]['id'])
" 2>/dev/null || echo "")
echo "✅ GROUPE_ID = $GROUPE_ID"


# ── [07.2] CRÉER un groupe ─────────────────────────────────────
# POST /groupes/
curl -s -X POST "$BASE_URL/groupes/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "code": "enseignants.lycee.libreville",
    "nom": "Enseignants — Lycée de Libreville",
    "description": "Groupe des enseignants du lycée Omar Bongo — Libreville",
    "type_groupe": "fonctionnel",
    "actif": true
  }' | tee /tmp/new_groupe.json | python3 -m json.tool

export NEW_GROUPE_ID=$(cat /tmp/new_groupe.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "✅ NEW_GROUPE_ID = $NEW_GROUPE_ID"


# ── [07.3] DÉTAIL d'un groupe ──────────────────────────────────
# GET /groupes/{id}
curl -s -X GET "$BASE_URL/groupes/$NEW_GROUPE_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [07.4] MODIFIER un groupe ──────────────────────────────────
# PUT /groupes/{id}
curl -s -X PUT "$BASE_URL/groupes/$NEW_GROUPE_ID" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "nom": "Enseignants — Lycée Omar Bongo",
    "description": "Groupe officiel — corps enseignant du Lycée Omar Bongo, Libreville"
  }' | python3 -m json.tool


# ── [07.5] AJOUTER des membres à un groupe ─────────────────────
# POST /groupes/{id}/membres
curl -s -X POST "$BASE_URL/groupes/$NEW_GROUPE_ID/membres" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"profil_ids\": [\"$PROFIL_ID\", \"$PROFIL_SANS_CRED_ID\"]
  }" | python3 -m json.tool


# ── [07.6] LISTER les membres d'un groupe ──────────────────────
# GET /groupes/{id}/membres
curl -s -X GET "$BASE_URL/groupes/$NEW_GROUPE_ID/membres" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [07.7] RETIRER un membre d'un groupe ───────────────────────
# DELETE /groupes/{id}/membres/{profil_id}
curl -s -X DELETE "$BASE_URL/groupes/$NEW_GROUPE_ID/membres/$PROFIL_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [07.8] AJOUTER des permissions à un groupe ─────────────────
# POST /groupes/{id}/permissions/ajouter
curl -s -X POST "$BASE_URL/groupes/$NEW_GROUPE_ID/permissions/ajouter" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"permission_ids\": [\"$PERMISSION_ID\"]
  }" | python3 -m json.tool


# ── [07.9] RETIRER des permissions d'un groupe ─────────────────
# POST /groupes/{id}/permissions/retirer
curl -s -X POST "$BASE_URL/groupes/$NEW_GROUPE_ID/permissions/retirer" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"permission_ids\": [\"$PERMISSION_ID\"]
  }" | python3 -m json.tool


# ── [07.10] ASSIGNER un rôle à un groupe ───────────────────────
# POST /groupes/{id}/roles
curl -s -X POST "$BASE_URL/groupes/$NEW_GROUPE_ID/roles" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"role_id\": \"$ROLE_ID\",
    \"raison\": \"Rôle par défaut pour tous les enseignants\"
  }" | python3 -m json.tool


# ── [07.11] SUPPRIMER un groupe ────────────────────────────────
# DELETE /groupes/{id}
curl -s -X DELETE "$BASE_URL/groupes/$NEW_GROUPE_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ================================================================
# MODULE 08 — AUDIT (Journal d'activité)
# Dépendances : ACCESS_TOKEN, PROFIL_ID
# Lecture seule — ne rien écrire directement
# ================================================================

# ── [08.1] MON JOURNAL (profil connecté) ───────────────────────
# GET /audit/moi?skip=0&limit=20
curl -s -X GET "$BASE_URL/audit/moi?skip=0&limit=20" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [08.2] JOURNAL d'un profil spécifique (admin) ──────────────
# GET /audit/profil/{profil_id}?skip=0&limit=20
curl -s -X GET "$BASE_URL/audit/profil/$PROFIL_ID?skip=0&limit=20" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [08.3] JOURNAL GLOBAL — Tous les événements (admin) ────────
# GET /audit/?skip=0&limit=50
curl -s -X GET "$BASE_URL/audit/?skip=0&limit=50" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [08.4] FILTRER — Événements refusés uniquement ─────────────
# GET /audit/?autorise=false&limit=50
curl -s -X GET "$BASE_URL/audit/?autorise=false&limit=50" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [08.5] FILTRER — Par module ────────────────────────────────
# GET /audit/?module=profils&limit=30
curl -s -X GET "$BASE_URL/audit/?module=profils&limit=30" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [08.6] FILTRER — Par plage de dates ────────────────────────
# GET /audit/?date_debut=2024-01-01&date_fin=2024-12-31
curl -s -X GET "$BASE_URL/audit/?date_debut=2024-01-01T00:00:00&date_fin=2025-12-31T23:59:59&limit=100" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [08.7] STATISTIQUES D'AUDIT (admin) ────────────────────────
# GET /audit/stats
curl -s -X GET "$BASE_URL/audit/stats" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ================================================================
# MODULE 09 — GATEWAY (Vérification des accès externes)
# Dépendances : ACCESS_TOKEN
# Utilisé par les microservices pour vérifier les permissions
# ================================================================

# ── [09.1] VÉRIFIER une permission (check externe) ─────────────
# POST /gateway/check
curl -s -X POST "$BASE_URL/gateway/check" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "permission_code": "iam.profil.lire",
    "profil_id": null
  }' | python3 -m json.tool


# ── [09.2] VÉRIFIER plusieurs permissions en une fois ──────────
# POST /gateway/check-multiple
curl -s -X POST "$BASE_URL/gateway/check-multiple" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "permission_codes": [
      "iam.profil.lire",
      "iam.profil.modifier",
      "iam.role.creer"
    ]
  }' | python3 -m json.tool


# ── [09.3] INFO du token appelant ──────────────────────────────
# GET /gateway/token-info
curl -s -X GET "$BASE_URL/gateway/token-info" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [09.4] INTROSPECT — Détail complet du profil connecté ──────
# GET /gateway/introspect
curl -s -X GET "$BASE_URL/gateway/introspect" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ================================================================
# MODULE 10 — ADMINISTRATION (admin uniquement)
# Dépendances : ACCESS_TOKEN avec droits admin (iam.admin.all)
# ================================================================

# ── [10.1] STATISTIQUES GLOBALES du système ────────────────────
# GET /admin/stats
curl -s -X GET "$BASE_URL/admin/stats" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [10.2] SANTÉ DU SYSTÈME ────────────────────────────────────
# GET /admin/health
curl -s -X GET "$BASE_URL/admin/health" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [10.3] NETTOYAGE des tokens expirés ────────────────────────
# POST /admin/cleanup-tokens
curl -s -X POST "$BASE_URL/admin/cleanup-tokens" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [10.4] SEEDS — Initialiser les données de base ─────────────
# POST /admin/seeds (⚠️  à utiliser en développement uniquement)
curl -s -X POST "$BASE_URL/admin/seeds" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "create_admin": true,
    "create_sample_roles": true,
    "create_sample_permissions": true
  }' | python3 -m json.tool


# ── [10.5] EXPORTER la configuration IAM ───────────────────────
# GET /admin/export
curl -s -X GET "$BASE_URL/admin/export" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [10.6] LISTE DES UTILISATEURS CONNECTÉS (admin) ───────────
# GET /admin/sessions-actives
curl -s -X GET "$BASE_URL/admin/sessions-actives" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ── [10.7] FORCER LA DÉCONNEXION d'un profil (admin) ───────────
# POST /admin/force-logout/{profil_id}
curl -s -X POST "$BASE_URL/admin/force-logout/$PROFIL_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool


# ================================================================
# FLUX COMPLET DE TEST — Séquence de bout en bout
# Vérifie que toute la chaîne fonctionne de A à Z
# ================================================================

echo ""
echo "======================================================="
echo "  FLUX COMPLET — Récapitulatif des variables collectées"
echo "======================================================="
echo "ACCESS_TOKEN       = ${ACCESS_TOKEN:0:40}..."
echo "REFRESH_TOKEN      = ${REFRESH_TOKEN:0:40}..."
echo "SESSION_ID         = $SESSION_ID"
echo "MON_PROFIL_ID      = $MON_PROFIL_ID"
echo "PROFIL_ID          = $PROFIL_ID"
echo "PROFIL_SANS_CRED_ID= $PROFIL_SANS_CRED_ID"
echo "ROLE_ID            = $ROLE_ID"
echo "NEW_ROLE_ID        = $NEW_ROLE_ID"
echo "PERMISSION_ID      = $PERMISSION_ID"
echo "PERMISSION_ID_2    = $PERMISSION_ID_2"
echo "NEW_PERMISSION_ID  = $NEW_PERMISSION_ID"
echo "CUSTOM_PERM_ID     = $CUSTOM_PERM_ID"
echo "SOURCE_ID          = $SOURCE_ID"
echo "SOURCE_CODE        = $SOURCE_CODE"
echo "GROUPE_ID          = $GROUPE_ID"
echo "NEW_GROUPE_ID      = $NEW_GROUPE_ID"
echo "ASSIGNATION_ID     = $ASSIGNATION_ID"
echo "TOKEN_CONFIG_ID    = $TOKEN_CONFIG_ID"
echo "======================================================="


# ================================================================
# LOGOUT FINAL — Fermer proprement la session de test
# ================================================================

# ── [FINAL] LOGOUT ─────────────────────────────────────────────
curl -s -X POST "$BASE_URL/tokens/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -m json.tool

echo ""
echo "✅ Session fermée — toutes les requêtes de test exécutées."