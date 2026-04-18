from app.repositories.base import BaseRepository
from app.repositories.permission import (
    PermissionRepository,
    PermissionSourceRepository,
)
from app.repositories.role import RoleRepository
from app.repositories.groupe import GroupeRepository
from app.repositories.profil_local import ProfilLocalRepository
from app.repositories.assignation_role import AssignationRoleRepository
from app.repositories.assignation_groupe import AssignationGroupeRepository
from app.repositories.journal_acces import JournalAccesRepository

__all__ = [
    "BaseRepository",
    "PermissionRepository",
    "PermissionSourceRepository",
    "RoleRepository",
    "GroupeRepository",
    "ProfilLocalRepository",
    "AssignationRoleRepository",
    "AssignationGroupeRepository",
    "JournalAccesRepository",
]
