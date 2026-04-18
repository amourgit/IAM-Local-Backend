# Commandes CURL pour Tester les API IAM Local

## Configuration Initiale

```bash
# Variables d'environnement
export IAM_BASE_URL="http://localhost:8000/api/v1"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="admin123"
export ETUDIANT_USERNAME="etudiant001"
export ETUDIANT_PASSWORD="password123"
export ENSEIGNANT_USERNAME="enseignant001"
export ENSEIGNANT_PASSWORD="password123"

# Variables à stocker (seront remplies pendant les tests)
export ADMIN_ACCESS_TOKEN=""
export ETUDIANT_ACCESS_TOKEN=""
export ENSEIGNANT_ACCESS_TOKEN=""
export ADMIN_PROFIL_ID=""
export ETUDIANT_PROFIL_ID=""
export ENSEIGNANT_PROFIL_ID=""
export ROLE_ETUDIANT_ID=""
export ROLE_ENSEIGNANT_ID=""
export GROUPE_L1_INFO_ID=""
export SOURCE_SCOLARITE_ID=""
export PERMISSION_INSCRIPTION_CREER_ID=""
export PERMISSION_INSCRIPTION_CONSULTER_ID=""
export PERMISSION_INSCRIPTION_MODIFIER_ID=""
export PERMISSION_INSCRIPTION_SUPPRIMER_ID=""
```

---

## Phase 1: Authentification

### 1.1 Login Admin
```bash
echo "=== Login Admin ==="
ADMIN_LOGIN_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/tokens/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "'${ADMIN_USERNAME}'",
    "password": "'${ADMIN_PASSWORD}'"
  }')

echo "$ADMIN_LOGIN_RESPONSE" | jq .
export ADMIN_ACCESS_TOKEN=$(echo "$ADMIN_LOGIN_RESPONSE" | jq -r '.access_token')
echo "Admin Access Token: ${ADMIN_ACCESS_TOKEN:0:50}..."
```

### 1.2 Login Étudiant
```bash
echo "=== Login Étudiant ==="
ETUDIANT_LOGIN_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/tokens/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "'${ETUDIANT_USERNAME}'",
    "password": "'${ETUDIANT_PASSWORD}'"
  }')

echo "$ETUDIANT_LOGIN_RESPONSE" | jq .
export ETUDIANT_ACCESS_TOKEN=$(echo "$ETUDIANT_LOGIN_RESPONSE" | jq -r '.access_token')
echo "Étudiant Access Token: ${ETUDIANT_ACCESS_TOKEN:0:50}..."
```

### 1.3 Login Enseignant
```bash
echo "=== Login Enseignant ==="
ENSEIGNANT_LOGIN_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/tokens/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "'${ENSEIGNANT_USERNAME}'",
    "password": "'${ENSEIGNANT_PASSWORD}'"
  }')

echo "$ENSEIGNANT_LOGIN_RESPONSE" | jq .
export ENSEIGNANT_ACCESS_TOKEN=$(echo "$ENSEIGNANT_LOGIN_RESPONSE" | jq -r '.access_token')
echo "Enseignant Access Token: ${ENSEIGNANT_ACCESS_TOKEN:0:50}..."
```

### 1.4 Valider Token Admin
```bash
echo "=== Validation Token Admin ==="
curl -s -X POST "${IAM_BASE_URL}/tokens/validate" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "'${ADMIN_ACCESS_TOKEN}'",
    "token_type": "access"
  }' | jq .
```

---

## Phase 2: Permissions

### 2.1 Créer Source Scolarité
```bash
echo "=== Créer Source Scolarité ==="
SOURCE_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/permissions/sources" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "scolarite",
    "nom": "Module Scolarité",
    "description": "Gestion de la scolarité",
    "version": "1.0.0",
    "url_base": "http://localhost:8001"
  }')

echo "$SOURCE_RESPONSE" | jq .
export SOURCE_SCOLARITE_ID=$(echo "$SOURCE_RESPONSE" | jq -r '.id')
echo "Source Scolarité ID: $SOURCE_SCOLARITE_ID"
```

### 2.2 Enregistrer Permissions Scolarité
```bash
echo "=== Enregistrer Permissions Scolarité ==="
PERMISSIONS_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/permissions/enregistrer" \
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
  }')

echo "$PERMISSIONS_RESPONSE" | jq .
```

### 2.3 Lister Permissions
```bash
echo "=== Lister Permissions ==="
curl -s -X GET "${IAM_BASE_URL}/permissions?domaine=scolarite&skip=0&limit=100" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 2.4 Récupérer IDs des Permissions
```bash
echo "=== Récupérer IDs des Permissions ==="
PERMISSIONS_LIST=$(curl -s -X GET "${IAM_BASE_URL}/permissions?domaine=scolarite&skip=0&limit=100" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}")

export PERMISSION_INSCRIPTION_CREER_ID=$(echo "$PERMISSIONS_LIST" | jq -r '.[] | select(.code=="scolarite.inscription.creer") | .id')
export PERMISSION_INSCRIPTION_CONSULTER_ID=$(echo "$PERMISSIONS_LIST" | jq -r '.[] | select(.code=="scolarite.inscription.consulter") | .id')
export PERMISSION_INSCRIPTION_MODIFIER_ID=$(echo "$PERMISSIONS_LIST" | jq -r '.[] | select(.code=="scolarite.inscription.modifier") | .id')
export PERMISSION_INSCRIPTION_SUPPRIMER_ID=$(echo "$PERMISSIONS_LIST" | jq -r '.[] | select(.code=="scolarite.inscription.supprimer") | .id')

echo "Permission Créer ID: $PERMISSION_INSCRIPTION_CREER_ID"
echo "Permission Consulter ID: $PERMISSION_INSCRIPTION_CONSULTER_ID"
echo "Permission Modifier ID: $PERMISSION_INSCRIPTION_MODIFIER_ID"
echo "Permission Supprimer ID: $PERMISSION_INSCRIPTION_SUPPRIMER_ID"
```

---

## Phase 3: Rôles

### 3.1 Créer Rôle Étudiant
```bash
echo "=== Créer Rôle Étudiant ==="
ROLE_ETUDIANT_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/roles/" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "etudiant",
    "nom": "Étudiant",
    "description": "Rôle de base pour les étudiants",
    "type_role": "FONCTIONNEL",
    "perimetre_obligatoire": false,
    "permissions_ids": []
  }')

echo "$ROLE_ETUDIANT_RESPONSE" | jq .
export ROLE_ETUDIANT_ID=$(echo "$ROLE_ETUDIANT_RESPONSE" | jq -r '.id')
echo "Rôle Étudiant ID: $ROLE_ETUDIANT_ID"
```

### 3.2 Créer Rôle Enseignant
```bash
echo "=== Créer Rôle Enseignant ==="
ROLE_ENSEIGNANT_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/roles/" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "enseignant",
    "nom": "Enseignant",
    "description": "Rôle pour les enseignants",
    "type_role": "FONCTIONNEL",
    "perimetre_obligatoire": false,
    "permissions_ids": []
  }')

echo "$ROLE_ENSEIGNANT_RESPONSE" | jq .
export ROLE_ENSEIGNANT_ID=$(echo "$ROLE_ENSEIGNANT_RESPONSE" | jq -r '.id')
echo "Rôle Enseignant ID: $ROLE_ENSEIGNANT_ID"
```

### 3.3 Ajouter Permissions au Rôle Étudiant
```bash
echo "=== Ajouter Permissions au Rôle Étudiant ==="
curl -s -X POST "${IAM_BASE_URL}/roles/${ROLE_ETUDIANT_ID}/permissions/ajouter" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permissions_ids": ["'${PERMISSION_INSCRIPTION_CONSULTER_ID}'"],
    "raison": "Permissions de base pour étudiants"
  }' | jq .
```

### 3.4 Ajouter Permissions au Rôle Enseignant
```bash
echo "=== Ajouter Permissions au Rôle Enseignant ==="
curl -s -X POST "${IAM_BASE_URL}/roles/${ROLE_ENSEIGNANT_ID}/permissions/ajouter" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permissions_ids": [
      "'${PERMISSION_INSCRIPTION_CREER_ID}'",
      "'${PERMISSION_INSCRIPTION_CONSULTER_ID}'",
      "'${PERMISSION_INSCRIPTION_MODIFIER_ID}'"
    ],
    "raison": "Permissions complètes pour enseignants"
  }' | jq .
```

### 3.5 Lister Rôles
```bash
echo "=== Lister Rôles ==="
curl -s -X GET "${IAM_BASE_URL}/roles?skip=0&limit=50" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 3.6 Détail Rôle Étudiant
```bash
echo "=== Détail Rôle Étudiant ==="
curl -s -X GET "${IAM_BASE_URL}/roles/${ROLE_ETUDIANT_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

---

## Phase 4: Profils

### 4.1 Créer Profil Étudiant avec Credentials
```bash
echo "=== Créer Profil Étudiant ==="
ETUDIANT_PROFIL_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/profils/" \
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
  }')

echo "$ETUDIANT_PROFIL_RESPONSE" | jq .
export ETUDIANT_PROFIL_ID=$(echo "$ETUDIANT_PROFIL_RESPONSE" | jq -r '.id')
echo "Profil Étudiant ID: $ETUDIANT_PROFIL_ID"
```

### 4.2 Créer Profil Enseignant avec Credentials
```bash
echo "=== Créer Profil Enseignant ==="
ENSEIGNANT_PROFIL_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/profils/" \
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
  }')

echo "$ENSEIGNANT_PROFIL_RESPONSE" | jq .
export ENSEIGNANT_PROFIL_ID=$(echo "$ENSEIGNANT_PROFIL_RESPONSE" | jq -r '.id')
echo "Profil Enseignant ID: $ENSEIGNANT_PROFIL_ID"
```

### 4.3 Lister Profils
```bash
echo "=== Lister Profils ==="
curl -s -X GET "${IAM_BASE_URL}/profils?skip=0&limit=50" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 4.4 Détail Profil Étudiant
```bash
echo "=== Détail Profil Étudiant ==="
curl -s -X GET "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 4.5 Assigner Rôle Étudiant
```bash
echo "=== Assigner Rôle Étudiant ==="
ETUDIANT_ROLE_ASSIGN=$(curl -s -X POST "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "'${ROLE_ETUDIANT_ID}'",
    "perimetre": {"classe": "L1"},
    "raison": "Assignation rôle étudiant de base"
  }')

echo "$ETUDIANT_ROLE_ASSIGN" | jq .
export ETUDIANT_ROLE_ASSIGN_ID=$(echo "$ETUDIANT_ROLE_ASSIGN" | jq -r '.id')
```

### 4.6 Assigner Rôle Enseignant
```bash
echo "=== Assigner Rôle Enseignant ==="
ENSEIGNANT_ROLE_ASSIGN=$(curl -s -X POST "${IAM_BASE_URL}/profils/${ENSEIGNANT_PROFIL_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "'${ROLE_ENSEIGNANT_ID}'",
    "perimetre": {"specialite": "Informatique"},
    "raison": "Assignation rôle enseignant"
  }')

echo "$ENSEIGNANT_ROLE_ASSIGN" | jq .
export ENSEIGNANT_ROLE_ASSIGN_ID=$(echo "$ENSEIGNANT_ROLE_ASSIGN" | jq -r '.id')
```

### 4.7 Lister Rôles du Profil Étudiant
```bash
echo "=== Lister Rôles du Profil Étudiant ==="
curl -s -X GET "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 4.8 Modifier Profil Étudiant
```bash
echo "=== Modifier Profil Étudiant ==="
curl -s -X PUT "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jean.dupont.updated@example.com",
    "telephone": "+33612345679",
    "notes": "Profil mis à jour pour test"
  }' | jq .
```

---

## Phase 5: Groupes

### 5.1 Créer Groupe Classe L1 Info
```bash
echo "=== Créer Groupe Classe L1 Info ==="
GROUPE_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/groupes/" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "classe_L1_info",
    "nom": "Classe L1 Informatique",
    "description": "Groupe pour les étudiants de L1 info",
    "type_groupe": "FONCTIONNEL",
    "perimetre": {"classe": "L1", "specialite": "informatique"},
    "roles_ids": ["'${ROLE_ETUDIANT_ID}'"]
  }')

echo "$GROUPE_RESPONSE" | jq .
export GROUPE_L1_INFO_ID=$(echo "$GROUPE_RESPONSE" | jq -r '.id')
echo "Groupe L1 Info ID: $GROUPE_L1_INFO_ID"
```

### 5.2 Lister Groupes
```bash
echo "=== Lister Groupes ==="
curl -s -X GET "${IAM_BASE_URL}/groupes?skip=0&limit=50" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 5.3 Détail Groupe
```bash
echo "=== Détail Groupe ==="
curl -s -X GET "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 5.4 Ajouter Membre au Groupe
```bash
echo "=== Ajouter Membre au Groupe ==="
GROUPE_MEMBER_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}/membres" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "profil_id": "'${ETUDIANT_PROFIL_ID}'",
    "perimetre": {"classe": "L1"},
    "raison": "Inscription dans la classe L1 info"
  }')

echo "$GROUPE_MEMBER_RESPONSE" | jq .
export GROUPE_MEMBER_ASSIGN_ID=$(echo "$GROUPE_MEMBER_RESPONSE" | jq -r '.id')
```

### 5.5 Modifier Groupe
```bash
echo "=== Modifier Groupe ==="
curl -s -X PUT "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Groupe mis à jour pour les étudiants de L1 info 2024-2025",
    "notes": "Ajout de l'\''année scolaire"
  }' | jq .
```

---

## Phase 6: Habilitations

### 6.1 Vérifier Habilitations Étudiant
```bash
echo "=== Habilitations Étudiant ==="
curl -s -X GET "${IAM_BASE_URL}/habilitations/moi" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" | jq .
```

### 6.2 Vérifier Habilitations Enseignant
```bash
echo "=== Habilitations Enseignant ==="
curl -s -X GET "${IAM_BASE_URL}/habilitations/moi" \
  -H "Authorization: Bearer ${ENSEIGNANT_ACCESS_TOKEN}" | jq .
```

### 6.3 Vérifier Permission Spécifique (Étudiant)
```bash
echo "=== Vérifier Permission Étudiant ==="
curl -s -X POST "${IAM_BASE_URL}/habilitations/verifier" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permission_code": "scolarite.inscription.consulter",
    "perimetre": {"classe": "L1"},
    "contexte": {"module": "scolarite"}
  }' | jq .
```

### 6.4 Vérifier Permission Non Autorisée (Étudiant)
```bash
echo "=== Vérifier Permission Non Autorisée ==="
curl -s -X POST "${IAM_BASE_URL}/habilitations/verifier" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permission_code": "scolarite.inscription.supprimer",
    "perimetre": {"classe": "L1"},
    "contexte": {"module": "scolarite"}
  }' | jq .
```

### 6.5 Vérifier Permission Enseignant
```bash
echo "=== Vérifier Permission Enseignant ==="
curl -s -X POST "${IAM_BASE_URL}/habilitations/verifier" \
  -H "Authorization: Bearer ${ENSEIGNANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permission_code": "scolarite.inscription.creer",
    "perimetre": {"specialite": "informatique"},
    "contexte": {"module": "scolarite"}
  }' | jq .
```

---

## Phase 7: Gateway

### 7.1 Lister Modules Disponibles
```bash
echo "=== Lister Modules Gateway ==="
curl -s -X GET "${IAM_BASE_URL}/gateway/modules" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 7.2 Test Forward Consultation (Étudiant)
```bash
echo "=== Test Forward Consultation (Étudiant) ==="
curl -s -X POST "${IAM_BASE_URL}/gateway/forward" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "module": "scolarite",
    "path": "/api/v1/inscriptions",
    "method": "GET",
    "params": {
      "classe": "L1"
    }
  }' | jq .
```

### 7.3 Test Forward Création (Enseignant)
```bash
echo "=== Test Forward Création (Enseignant) ==="
curl -s -X POST "${IAM_BASE_URL}/gateway/forward" \
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
  }' | jq .
```

### 7.4 Test Forward Non Autorisé (Étudiant)
```bash
echo "=== Test Forward Non Autorisé (Étudiant) ==="
curl -s -X POST "${IAM_BASE_URL}/gateway/forward" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "module": "scolarite",
    "path": "/api/v1/inscriptions",
    "method": "DELETE",
    "body": {
      "inscription_id": "test-id"
    }
  }' | jq .
```

---

## Phase 8: Audit

### 8.1 Consulter Mon Journal (Étudiant)
```bash
echo "=== Journal Étudiant ==="
curl -s -X GET "${IAM_BASE_URL}/audit/moi?skip=0&limit=50" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}" | jq .
```

### 8.2 Journal Global (Admin)
```bash
echo "=== Journal Global Admin ==="
curl -s -X GET "${IAM_BASE_URL}/audit?skip=0&limit=100" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 8.3 Journal par Profil
```bash
echo "=== Journal par Profil Étudiant ==="
curl -s -X GET "${IAM_BASE_URL}/audit/profil/${ETUDIANT_PROFIL_ID}?skip=0&limit=50" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

---

## Phase 9: Configuration Tokens

### 9.1 Créer Configuration Token
```bash
echo "=== Créer Configuration Token ==="
TOKEN_CONFIG_RESPONSE=$(curl -s -X POST "${IAM_BASE_URL}/token-config/" \
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
  }')

echo "$TOKEN_CONFIG_RESPONSE" | jq .
export TOKEN_CONFIG_ID=$(echo "$TOKEN_CONFIG_RESPONSE" | jq -r '.id')
```

### 9.2 Lister Configurations
```bash
echo "=== Lister Configurations Tokens ==="
curl -s -X GET "${IAM_BASE_URL}/token-config/?skip=0&limit=10" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 9.3 Configuration Active
```bash
echo "=== Configuration Active ==="
curl -s -X GET "${IAM_BASE_URL}/token-config/active" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

---

## Phase 10: Tests de Modification

### 10.1 Modifier Rôle Étudiant
```bash
echo "=== Modifier Rôle Étudiant ==="
curl -s -X PUT "${IAM_BASE_URL}/roles/${ROLE_ETUDIANT_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Rôle étudiant mis à jour avec permissions étendues",
    "notes": "Mise à jour après tests"
  }' | jq .
```

### 10.2 Retirer Permission du Rôle Enseignant
```bash
echo "=== Retirer Permission Rôle Enseignant ==="
curl -s -X POST "${IAM_BASE_URL}/roles/${ROLE_ENSEIGNANT_ID}/permissions/retirer" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "permissions_ids": ["'${PERMISSION_INSCRIPTION_SUPPRIMER_ID}'"],
    "raison": "Retrait pour test"
  }' | jq .
```

### 10.3 Révoquer Rôle du Profil Étudiant
```bash
echo "=== Révoquer Rôle Profil Étudiant ==="
curl -s -X DELETE "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/roles/${ETUDIANT_ROLE_ASSIGN_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "raison": "Test révocation"
  }'
```

### 10.4 Suspendre Profil Étudiant
```bash
echo "=== Suspendre Profil Étudiant ==="
curl -s -X POST "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/suspendre" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "raison": "Test suspension"
  }' | jq .
```

### 10.5 Réactiver Profil Étudiant
```bash
echo "=== Réactiver Profil Étudiant ==="
curl -s -X POST "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/reactiver" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" | jq .
```

### 10.6 Réassigner Rôle Étudiant
```bash
echo "=== Réassigner Rôle Étudiant ==="
curl -s -X POST "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}/roles" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "'${ROLE_ETUDIANT_ID}'",
    "perimetre": {"classe": "L1"},
    "raison": "Réassignation après test"
  }' | jq .
```

---

## Phase 11: Nettoyage

### 11.1 Retirer Membre du Groupe
```bash
echo "=== Retirer Membre du Groupe ==="
curl -s -X DELETE "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}/membres/${GROUPE_MEMBER_ASSIGN_ID}?raison=Test suppression" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

### 11.2 Supprimer Groupe
```bash
echo "=== Supprimer Groupe ==="
curl -s -X DELETE "${IAM_BASE_URL}/groupes/${GROUPE_L1_INFO_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

### 11.3 Supprimer Rôles
```bash
echo "=== Supprimer Rôle Étudiant ==="
curl -s -X DELETE "${IAM_BASE_URL}/roles/${ROLE_ETUDIANT_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"

echo "=== Supprimer Rôle Enseignant ==="
curl -s -X DELETE "${IAM_BASE_URL}/roles/${ROLE_ENSEIGNANT_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

### 11.4 Supprimer Profils
```bash
echo "=== Supprimer Profil Étudiant ==="
curl -s -X DELETE "${IAM_BASE_URL}/profils/${ETUDIANT_PROFIL_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"

echo "=== Supprimer Profil Enseignant ==="
curl -s -X DELETE "${IAM_BASE_URL}/profils/${ENSEIGNANT_PROFIL_ID}" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

### 11.5 Logout
```bash
echo "=== Logout Admin ==="
curl -s -X POST "${IAM_BASE_URL}/tokens/logout" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"

echo "=== Logout Étudiant ==="
curl -s -X POST "${IAM_BASE_URL}/tokens/logout" \
  -H "Authorization: Bearer ${ETUDIANT_ACCESS_TOKEN}"

echo "=== Logout Enseignant ==="
curl -s -X POST "${IAM_BASE_URL}/tokens/logout" \
  -H "Authorization: Bearer ${ENSEIGNANT_ACCESS_TOKEN}"
```

---

## Script Complet d'Exécution

Pour exécuter tous les tests d'un coup :

```bash
#!/bin/bash

# Script de test complet pour IAM Local API
# Exécutez: chmod +x test_iam_complete.sh && ./test_iam_complete.sh

set -e  # Arrêter en cas d'erreur

echo "=== DÉBUT DES TESTS IAM LOCAL API ==="

# Charger les variables
source <(curl -s https://raw.githubusercontent.com/votre-repo/iam-test-env.sh)

# Exécuter chaque phase
echo -e "\n=== PHASE 1: AUTHENTIFICATION ==="
# [Coller les commandes de la phase 1 ici]

echo -e "\n=== PHASE 2: PERMISSIONS ==="
# [Coller les commandes de la phase 2 ici]

# ... continuer avec toutes les phases

echo -e "\n=== FIN DES TESTS ==="
echo "Tous les tests ont été exécutés avec succès!"
```

---

## Notes d'Utilisation

1. **Prérequis** : Installé `jq` pour le formatage JSON (`sudo apt install jq`)

2. **Exécution** : Copiez-collez chaque commande directement dans votre terminal

3. **Variables** : Les variables sont automatiquement stockées pendant l'exécution

4. **Erreurs** : Si une commande échoue, vérifiez que le serveur IAM est bien démarré

5. **Nettoyage** : La phase 11 supprime toutes les données créées pendant les tests

6. **Gateway** : Les tests de gateway nécessitent que les modules métier soient actifs
