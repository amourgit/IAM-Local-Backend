"""
Routes API — Profils Locaux.

Le ProfilLocal est l'UNITÉ DE BASE de toutes les opérations locales.
Chaque profil représente une inscription / un dossier scolaire.
Les tokens JWT, sessions Redis, permissions et rôles sont liés au profil.
"""
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser, require_permission
from app.services.profil_service import ProfilService
from app.schemas.profil_local import (
    ProfilLocalCreateSchema,
    ProfilLocalUpdateSchema,
    SuspendreProfilSchema,
    ProfilResponseSchema,
    ProfilListSchema,
    ProfilLocalWithCredentialsCreateSchema,
)
from app.schemas.assignation import (
    AssignationRoleCreateSchema,
    AssignationRoleResponseSchema,
    RevoquerAssignationSchema,
)

router = APIRouter(prefix="/profils", tags=["IAM — Profils"])


# ─────────────────────────────────────────────────────────────
#  CONSULTATION
# ─────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model = List[ProfilListSchema],
    summary        = "Lister les profils locaux",
    description    = (
        "Liste paginée des profils. "
        "Supporte la recherche sur les champs du profil ET du compte parent."
    ),
)
async def lister_profils(
    type_profil : Optional[str] = Query(None, description="etudiant, enseignant, personnel_admin..."),
    statut      : Optional[str] = Query(None, description="actif, suspendu, inactif, expire"),
    q           : Optional[str] = Query(None, description="Recherche sur nom, prénom, email, identifiant, username"),
    skip        : int           = Query(0,  ge=0),
    limit       : int           = Query(50, ge=1, le=200),
    db          : AsyncSession  = Depends(get_db),
    user        : CurrentUser   = Depends(require_permission("iam.profil.consulter")),
):
    svc = ProfilService(db)
    return await svc.get_all(
        skip=skip, limit=limit,
        type_profil=type_profil, statut=statut, q=q,
    )


@router.get(
    "/moi",
    response_model = ProfilResponseSchema,
    summary        = "Mon profil courant",
    description    = (
        "Retourne le profil de l'utilisateur connecté. "
        "C'est ce profil dont l'id est le sub du JWT actif."
    ),
)
async def mon_profil(
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    svc = ProfilService(db)
    return await svc.get_by_id(user.profil_id)


@router.get(
    "/moi/profils-disponibles",
    response_model = List[ProfilResponseSchema],
    summary        = "Mes profils disponibles",
    description    = (
        "Retourne tous les profils actifs du même compte que l'utilisateur connecté. "
        "Utile pour permettre à un utilisateur de changer de profil actif (changer d'inscription)."
    ),
)
async def mes_profils_disponibles(
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    svc    = ProfilService(db)
    profil = await svc.get_by_id(user.profil_id)
    return await svc.get_profils_du_compte(profil.compte_id)


@router.get(
    "/{profil_id}",
    response_model = ProfilResponseSchema,
    summary        = "Détail d'un profil",
)
async def get_profil(
    profil_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.profil.consulter")),
):
    svc = ProfilService(db)
    return await svc.get_by_id(profil_id)


@router.get(
    "/par-compte/{compte_id}",
    response_model = List[ProfilResponseSchema],
    summary        = "Profils d'un compte donné",
    description    = "Liste tous les profils (inscriptions) d'un compte local.",
)
async def get_profils_par_compte(
    compte_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.profil.consulter")),
):
    svc = ProfilService(db)
    return await svc.get_profils_du_compte(compte_id)


@router.get(
    "/par-compte/{compte_id}/count",
    summary = "Nombre de profils d'un compte",
)
async def compter_profils_par_compte(
    compte_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.profil.consulter")),
):
    svc     = ProfilService(db)
    profils = await svc.get_profils_du_compte(compte_id)
    return {
        "compte_id"      : str(compte_id),
        "nb_profils"     : len(profils),
        "profils_actifs" : sum(1 for p in profils if p.statut == "actif"),
        "par_type"       : {
            tp: sum(1 for p in profils if p.type_profil == tp)
            for tp in set(p.type_profil for p in profils)
        },
    }


@router.get(
    "/par-user-national/{user_id_national}",
    response_model = List[ProfilResponseSchema],
    summary        = "Profils par user_id_national IAM Central",
    description    = "Retourne tous les profils d'un utilisateur IAM Central dans cet établissement.",
)
async def get_profils_par_user_national(
    user_id_national : UUID,
    db               : AsyncSession = Depends(get_db),
    user             : CurrentUser  = Depends(require_permission("iam.profil.consulter")),
):
    from app.repositories.profil_local import ProfilLocalRepository
    from app.repositories.compte_local import CompteLocalRepository
    from app.core.exceptions import NotFoundError

    profil_repo = ProfilLocalRepository(db)
    compte_repo = CompteLocalRepository(db)
    profils     = await profil_repo.get_all_by_user_id_national(user_id_national)
    svc         = ProfilService(db)
    result      = []
    for p in profils:
        compte = await compte_repo.get_by_id(p.compte_id)
        result.append(svc._to_response(p, compte))
    return result


@router.get(
    "/stats/resume",
    summary     = "Statistiques globales des profils",
)
async def stats_profils(
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(require_permission("iam.profil.consulter")),
):
    from sqlalchemy import func, select
    from app.models.profil_local import ProfilLocal

    result_statut = await db.execute(
        select(ProfilLocal.statut, func.count(ProfilLocal.id).label("total"))
        .where(ProfilLocal.is_deleted == False)
        .group_by(ProfilLocal.statut)
    )
    result_type = await db.execute(
        select(ProfilLocal.type_profil, func.count(ProfilLocal.id).label("total"))
        .where(ProfilLocal.is_deleted == False)
        .group_by(ProfilLocal.type_profil)
    )
    par_statut = {row.statut: row.total for row in result_statut.all()}
    par_type   = {row.type_profil: row.total for row in result_type.all()}
    return {
        "total"     : sum(par_statut.values()),
        "par_statut": par_statut,
        "par_type"  : par_type,
    }


# ─────────────────────────────────────────────────────────────
#  CRÉATION
# ─────────────────────────────────────────────────────────────

@router.post(
    "/sans-credentials",
    response_model = ProfilResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Créer un profil rattaché à un CompteLocal existant",
    description    = (
        "Crée un nouveau profil (nouvelle inscription) pour un compte existant. "
        "Exemple : étudiant s'inscrivant dans une seconde filière."
    ),
)
async def creer_profil(
    data    : ProfilLocalCreateSchema,
    request : Request,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(require_permission("iam.profil.creer")),
):
    svc = ProfilService(db)
    return await svc.creer(
        data       = data,
        cree_par   = user.profil_id,
        request_id = getattr(request.state, "request_id", None),
    )


@router.post(
    "/",
    response_model = ProfilResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Créer un compte local + profil avec credentials",
    description    = (
        "Crée en une opération un CompteLocal (avec credentials) ET un ProfilLocal. "
        "Utilisé pour les utilisateurs sans accès SSO IAM Central."
    ),
)
async def creer_profil_avec_credentials(
    data    : ProfilLocalWithCredentialsCreateSchema,
    request : Request,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(require_permission("iam.profil.creer")),
):
    svc = ProfilService(db)
    return await svc.creer_avec_credentials(
        data       = data,
        cree_par   = user.profil_id,
        request_id = getattr(request.state, "request_id", None),
    )


# ─────────────────────────────────────────────────────────────
#  MODIFICATION
# ─────────────────────────────────────────────────────────────

@router.patch(
    "/{profil_id}",
    response_model = ProfilResponseSchema,
    summary        = "Mettre à jour un profil",
)
async def update_profil(
    profil_id : UUID,
    data      : ProfilLocalUpdateSchema,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.profil.modifier")),
):
    svc = ProfilService(db)
    return await svc.update(
        id         = profil_id,
        data       = data,
        updated_by = user.profil_id,
    )


@router.post(
    "/{profil_id}/suspendre",
    response_model = ProfilResponseSchema,
    summary        = "Suspendre un profil",
)
async def suspendre_profil(
    profil_id : UUID,
    data      : SuspendreProfilSchema,
    request   : Request,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.profil.suspendre")),
):
    svc = ProfilService(db)
    return await svc.suspendre(
        id         = profil_id,
        data       = data,
        suspend_by = user.profil_id,
        request_id = getattr(request.state, "request_id", None),
    )


@router.post(
    "/{profil_id}/reactiver",
    response_model = ProfilResponseSchema,
    summary        = "Réactiver un profil",
)
async def reactiver_profil(
    profil_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.profil.modifier")),
):
    svc = ProfilService(db)
    return await svc.reactiver(
        id         = profil_id,
        updated_by = user.profil_id,
    )


@router.delete(
    "/{profil_id}",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Supprimer un profil (soft delete)",
)
async def supprimer_profil(
    profil_id : UUID,
    request   : Request,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.profil.supprimer")),
):
    svc = ProfilService(db)
    await svc.supprimer(
        id         = profil_id,
        deleted_by = user.profil_id,
        request_id = getattr(request.state, "request_id", None),
    )


# ─────────────────────────────────────────────────────────────
#  RÔLES / ASSIGNATIONS
# ─────────────────────────────────────────────────────────────

@router.post(
    "/{profil_id}/roles",
    response_model = AssignationRoleResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Assigner un rôle à un profil",
)
async def assigner_role(
    profil_id : UUID,
    data      : AssignationRoleCreateSchema,
    request   : Request,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.role.assigner")),
):
    data.profil_id = profil_id
    svc = ProfilService(db)
    return await svc.assigner_role(
        data       = data,
        created_by = user.profil_id,
        request_id = getattr(request.state, "request_id", None),
    )


@router.delete(
    "/roles/{assignation_id}",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Révoquer un rôle d'un profil",
)
async def revoquer_role(
    assignation_id : UUID,
    data           : RevoquerAssignationSchema,
    request        : Request,
    db             : AsyncSession = Depends(get_db),
    user           : CurrentUser  = Depends(require_permission("iam.role.revoquer")),
):
    svc = ProfilService(db)
    await svc.revoquer_role(
        assignation_id = assignation_id,
        revoque_par    = user.profil_id,
        data           = data,
        request_id     = getattr(request.state, "request_id", None),
    )
