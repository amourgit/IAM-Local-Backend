# Gateway & Endpoint Permission Architecture

## Vue d'ensemble

L'IAM Local implémente une architecture d'**Authorization Gateway** :

1. **IAM Local = Auth Gateway** : Valide JWT, charge identité, injecte contexte
2. **Chaque Module = Authz Local** : Valide permissions, logique métier
3. **EndpointPermission Registry** : Catalogue centralisé des endpoints et leurs permissions requises

---

## Flux complet

### Phase 1 : Démarrage du module (ex: Scolarité)

À sa mise en service, chaque module fournit **un simple JSON** listant ses
permissions de base (code, nom, description, niveau de risque, etc.) et
ses endpoints associés. Il n'a **pas besoin de connaître ni de prédéfinir
des UUID** : IAM Local crée automatiquement les permissions et attribue
les UUID en base. Les permissions sont enregistrées avec un
`source_id` pointant vers le module déclarant.

La requête peut être refaite à chaque redémarrage ; IAM Local ignorera
les codes déjà présents et mettra à jour les métadonnées si nécessaire.

```python
# scolarite/app/constants.py ou un fichier JSON
PERMISSIONS_METADATA = [
    {
        "code": "scolarite.inscription.creer",
        "nom": "Créer une inscription",
        "description": "Autorise la création d'une inscription",
        "domaine": "scolarite",
        "ressource": "inscription",
        "action": "creer",
        "niveau_risque": "MOYEN",
    },
    # ...
]

# scolarite/app/main.py (startup)
@app.on_event("startup")
async def register_permissions_and_endpoints():
    async with httpx.AsyncClient() as client:
        # enregistrer les permissions de base
        await client.post(
            "http://iam-local:8002/api/v1/permissions/enregistrer",
            json={
                "source_code": "scolarite",
                "source_nom": "Module Scolarité",
                "source_version": "1.1.0",
                "source_url": "http://scolarite:8003",
                "permissions": PERMISSIONS_METADATA,
            },
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
        )

        # puis enregistrer les endpoints comme avant
        await client.post(
            "http://iam-local:8002/api/v1/endpoints/register",
            json={
                "source_code": "scolarite",
                "module": "scolarite",
                "version": "1.1.0",
                "endpoints": [
                    {
                        "path": "/api/v1/inscriptions",
                        "method": "POST",
                        "permission_ids": ["scolarite.inscription.creer"],
                        "description": "Créer une inscription"
                    }
                ]
            },
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
        )
```

IAM Local stocke dans `endpoint_permissions` :

```
module_source_id | path                  | method | permission_uuids
-----------------+-----------------------+--------+-----------------------------
<scolarite_src>  | /api/v1/inscriptions  | POST   | [a1b2c3d4-e5f6-7890-abcd-ef1234567890]
```

### Phase 2 : Requête utilisateur

```
Frontend
  ↓ POST /api/v1/scolarite/inscriptions + Bearer JWT

IAM Local Gateway Middleware
  1. Valide JWT → profil_id, établissement_id, [permissions]
  2. is_internal_path("/api/v1/scolarite/...") ? NON
  3. extract_module_from_path() → "scolarite"
  4. Lookup source par code "scolarite"
  5. EndpointPermissionService.get_for_request(source_id, "/api/v1/scolarite/inscriptions", "POST")
     → retourne { permission_uuids: [a1b2c3d4...] }
  6. Vérifie : user.permissions ∩ [a1b2c3d4...] ≠ ∅ ? OUI
  7. Audit log : OK
  8. Proxifie : http://scolarite:8003/api/v1/inscriptions
  9. Injecte headers :
       x-user-id: usr_123
       x-user-permissions: a1b2c3d4-e5f6-7890-abcd-ef1234567890,...

Scolarité Module
  1. Reçoit requête proxifiée
  2. Logique métier : période ouverte ? quota ? règles établissement ?
  3. Répond 201 Created
```

---

## Composants implémentés

### Modèles

| Modèle | Rôle |
|--------|------|
| `EndpointPermission` | Registre (source_id, path, method, permission_uuids[]) |

### Services

| Service | Méthodes |
|---------|----------|
| `EndpointPermissionService` | `register_endpoints()`, `get_for_request()`, `list_by_source()` |
| `PermissionService` | `create()`, `update()`, `enregistrement_masse()`, `create_custom_permission()` |

### Repositories

| Repository | Opérations |
|------------|-----------|
| `EndpointPermissionRepository` | CRUD, `get_by_source()`, `get_by_path_method()`, `replace_for_source()` |

### API Endpoints

| Endpoint | Méthode | Qui | Rôle |
|----------|---------|-----|------|
| `/endpoints/register` | POST | Modules | Enregistrer leurs endpoints |
| `/endpoints/` | GET | Admin | Lister endpoints d'un module |
| `/admin/endpoints` | GET | Admin | Voir TOUS les endpoints (affichage) |
| `/admin/endpoints/by-module/{code}` | GET | Admin | Endpoints d'un module spécifique |
| `/permissions/custom` | POST | Admin | Créer permission custom |

### Middleware

| Middleware | Rôle |
|-----------|------|
| `GatewayMiddleware` | Auth + Authz structurelle + proxification |

### Utilitaires

| Module | Fonctions |
|--------|-----------|
| `gateway_helpers` | `extract_module_from_path()`, `get_module_url()`, `is_internal_path()` |

---

---

## Configuration

### Module Routes (dans `gateway_helpers.py`)

```python
MODULE_ROUTES = {
    "scolarite": "http://scolarite:8003",
    "pedagogie": "http://pedagogie:8004",
    "examens": "http://examens:8005",
    ...
}
```

Récupérés depuis `settings.get()` (env vars) pour flexibilité.

### Paths Internes (ne sont pas proxifiés)

```python
/docs
/redoc
/health
/api/v1/auth/...
/api/v1/permissions/...
/api/v1/roles/...
/api/v1/endpoints/...
/api/v1/admin/...
```

---

## Prochaines étapes

- [ ] Ajouter signature JWT pour X-User-Context (sécurité)
- [ ] Implémenter worker Kafka pour sync permissions custom
- [ ] Ajouter circuit breaker si module indisponible
- [ ] Tests unitaires + intégration
- [ ] Documenter pour les modules (comment enregistrer)
