"""
Routes API — Comptes Locaux.

Le CompteLocal représente l'identité consolidée d'un utilisateur.
Il porte le lien avec IAM Central et peut avoir plusieurs profils
(inscriptions dans différentes filières).
"""
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user, CurrentUser, require_permission
from app.services.compte_local_service import CompteLocalService
from app.services.profil_service import ProfilService
from app.schemas.compte_local import (
    CompteLocalCreateSchema,
    CompteLocalUpdateSchema,
    SuspendreCompteSchema,
    CompteLocalResponseSchema,
    CompteLocalListSchema,
)
from app.schemas.profil_local import ProfilResponseSchema, ProfilListSchema

router = APIRouter(prefix="/comptes", tags=["IAM — Comptes Locaux"])


# ─────────────────────────────────────────────────────────────
#  CONSULTATION
# ─────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model = List[CompteLocalListSchema],
    summary        = "Lister tous les comptes locaux",
    description    = (
        "Liste paginée des comptes locaux. "
        "Supporte la recherche full-text et le filtre par statut."
    ),
)
async def lister_comptes(
    statut : Optional[str] = Query(None, description="Filtre par statut : actif, suspendu, inactif"),
    q      : Optional[str] = Query(None, description="Recherche sur nom, prénom, email, identifiant national"),
    skip   : int           = Query(0,  ge=0),
    limit  : int           = Query(50, ge=1, le=200),
    db     : AsyncSession  = Depends(get_db),
    user   : CurrentUser   = Depends(require_permission("iam.compte.consulter")),
):
    svc = CompteLocalService(db)
    return await svc.get_all(skip=skip, limit=limit, statut=statut, q=q)


@router.get(
    "/moi",
    response_model = CompteLocalResponseSchema,
    summary        = "Mon compte local",
    description    = "Retourne le CompteLocal de l'utilisateur connecté (via profil courant).",
)
async def mon_compte(
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(get_current_user),
):
    # Récupérer le compte via le profil connecté
    profil_svc = ProfilService(db)
    profil     = await profil_svc.get_by_id(user.profil_id)
    svc        = CompteLocalService(db)
    return await svc.get_with_profils(profil.compte_id)


@router.get(
    "/{compte_id}",
    response_model = CompteLocalResponseSchema,
    summary        = "Détail d'un compte local",
)
async def get_compte(
    compte_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.compte.consulter")),
):
    svc = CompteLocalService(db)
    return await svc.get_with_profils(compte_id)


@router.get(
    "/{compte_id}/profils",
    response_model = List[ProfilResponseSchema],
    summary        = "Profils d'un compte local",
    description    = (
        "Retourne tous les profils (inscriptions) d'un compte local. "
        "Un étudiant inscrit dans deux filières aura deux profils ici."
    ),
)
async def get_profils_du_compte(
    compte_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.compte.consulter")),
):
    svc = ProfilService(db)
    return await svc.get_profils_du_compte(compte_id)


@router.get(
    "/{compte_id}/profils/count",
    summary = "Nombre de profils d'un compte",
    description = "Retourne le nombre total de profils rattachés à un compte local.",
)
async def compter_profils_du_compte(
    compte_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.compte.consulter")),
):
    svc     = ProfilService(db)
    profils = await svc.get_profils_du_compte(compte_id)
    return {
        "compte_id"   : str(compte_id),
        "nb_profils"  : len(profils),
        "profils_actifs": sum(1 for p in profils if p.statut == "actif"),
    }


@router.get(
    "/recherche/par-identifiant/{identifiant_national}",
    response_model = CompteLocalResponseSchema,
    summary        = "Chercher un compte par identifiant national",
)
async def get_compte_par_identifiant(
    identifiant_national : str,
    db                   : AsyncSession = Depends(get_db),
    user                 : CurrentUser  = Depends(require_permission("iam.compte.consulter")),
):
    from app.repositories.compte_local import CompteLocalRepository
    from app.core.exceptions import NotFoundError
    repo   = CompteLocalRepository(db)
    compte = await repo.get_by_identifiant_national(identifiant_national)
    if not compte:
        raise NotFoundError("CompteLocal", identifiant_national)
    svc = CompteLocalService(db)
    return await svc.get_with_profils(compte.id)


@router.get(
    "/recherche/par-email/{email}",
    response_model = CompteLocalResponseSchema,
    summary        = "Chercher un compte par email",
)
async def get_compte_par_email(
    email : str,
    db    : AsyncSession = Depends(get_db),
    user  : CurrentUser  = Depends(require_permission("iam.compte.consulter")),
):
    from app.repositories.compte_local import CompteLocalRepository
    from app.core.exceptions import NotFoundError
    repo   = CompteLocalRepository(db)
    compte = await repo.get_by_email(email)
    if not compte:
        raise NotFoundError("CompteLocal", email)
    svc = CompteLocalService(db)
    return await svc.get_with_profils(compte.id)


@router.get(
    "/recherche/par-user-national/{user_id_national}",
    response_model = CompteLocalResponseSchema,
    summary        = "Chercher un compte par user_id_national (IAM Central)",
)
async def get_compte_par_user_national(
    user_id_national : UUID,
    db               : AsyncSession = Depends(get_db),
    user             : CurrentUser  = Depends(require_permission("iam.compte.consulter")),
):
    from app.repositories.compte_local import CompteLocalRepository
    from app.core.exceptions import NotFoundError
    repo   = CompteLocalRepository(db)
    compte = await repo.get_by_user_id_national(user_id_national)
    if not compte:
        raise NotFoundError("CompteLocal", str(user_id_national))
    svc = CompteLocalService(db)
    return await svc.get_with_profils(compte.id)


# ─────────────────────────────────────────────────────────────
#  CRÉATION
# ─────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model = CompteLocalResponseSchema,
    status_code    = status.HTTP_201_CREATED,
    summary        = "Créer un compte local manuellement",
    description    = "Crée un compte local sans credentials (SSO uniquement).",
)
async def creer_compte(
    data    : CompteLocalCreateSchema,
    request : Request,
    db      : AsyncSession = Depends(get_db),
    user    : CurrentUser  = Depends(require_permission("iam.compte.creer")),
):
    svc = CompteLocalService(db)
    return await svc.creer_manuel(
        data       = data,
        cree_par   = user.profil_id,
        request_id = getattr(request.state, "request_id", None),
    )


# ─────────────────────────────────────────────────────────────
#  MODIFICATION
# ─────────────────────────────────────────────────────────────

@router.patch(
    "/{compte_id}",
    response_model = CompteLocalResponseSchema,
    summary        = "Mettre à jour un compte local",
)
async def update_compte(
    compte_id : UUID,
    data      : CompteLocalUpdateSchema,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.compte.modifier")),
):
    svc = CompteLocalService(db)
    return await svc.update(
        id         = compte_id,
        data       = data,
        updated_by = user.profil_id,
    )


@router.post(
    "/{compte_id}/suspendre",
    response_model = CompteLocalResponseSchema,
    summary        = "Suspendre un compte local",
    description    = (
        "Suspendre un compte désactive TOUS ses profils associés "
        "en bloquant l'authentification."
    ),
)
async def suspendre_compte(
    compte_id : UUID,
    data      : SuspendreCompteSchema,
    request   : Request,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.compte.suspendre")),
):
    svc = CompteLocalService(db)
    return await svc.suspendre(
        id         = compte_id,
        data       = data,
        suspend_by = user.profil_id,
        request_id = getattr(request.state, "request_id", None),
    )


@router.post(
    "/{compte_id}/reactiver",
    response_model = CompteLocalResponseSchema,
    summary        = "Réactiver un compte local",
)
async def reactiver_compte(
    compte_id : UUID,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.compte.modifier")),
):
    svc = CompteLocalService(db)
    return await svc.reactiver(
        id         = compte_id,
        updated_by = user.profil_id,
    )


@router.delete(
    "/{compte_id}",
    status_code = status.HTTP_204_NO_CONTENT,
    summary     = "Supprimer un compte local (soft delete)",
)
async def supprimer_compte(
    compte_id : UUID,
    request   : Request,
    db        : AsyncSession = Depends(get_db),
    user      : CurrentUser  = Depends(require_permission("iam.compte.supprimer")),
):
    svc = CompteLocalService(db)
    await svc.supprimer(
        id         = compte_id,
        deleted_by = user.profil_id,
        request_id = getattr(request.state, "request_id", None),
    )


# ─────────────────────────────────────────────────────────────
#  STATS / AGRÉGATS
# ─────────────────────────────────────────────────────────────

@router.get(
    "/stats/resume",
    summary     = "Statistiques globales des comptes locaux",
    description = "Retourne les compteurs globaux (actifs, suspendus, par statut...)",
)
async def stats_comptes(
    db   : AsyncSession = Depends(get_db),
    user : CurrentUser  = Depends(require_permission("iam.compte.consulter")),
):
    from sqlalchemy import func, select
    from app.models.compte_local import CompteLocal

    result = await db.execute(
        select(
            CompteLocal.statut,
            func.count(CompteLocal.id).label("total")
        )
        .where(CompteLocal.is_deleted == False)
        .group_by(CompteLocal.statut)
    )
    rows = result.all()
    stats = {row.statut: row.total for row in rows}
    total = sum(stats.values())
    return {
        "total"     : total,
        "par_statut": stats,
    }
