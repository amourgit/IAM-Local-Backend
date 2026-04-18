"""
Service de gestion des événements d'inscription depuis Scolarité.
Flux complet :
1. Reçoit événement d'inscription soumise
2. Vérifie si profil existe (par identifiant_national)
3. Si existe → Audit doublon + Ignorer
4. Si n'existe pas → Appeller IAM Central pour infos complètes
5. Créer profil local avec credentials temporaires
6. Publier événement de succès/erreur
"""

import logging
from uuid import UUID
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.database import get_db_session
from app.repositories.profil_local import ProfilLocalRepository
from app.services.profil_service import ProfilService
from app.services.audit_service import AuditService
from app.services.credential_service import CredentialService
from app.infrastructure.kafka.producer import KafkaProducer
from app.infrastructure.kafka.topics import Topics
from app.core.exceptions import AlreadyExistsError, NotFoundError, ValidationError
from app.schemas.profil_local import ProfilLocalWithCredentialsCreateSchema
from app.core.enums import TypeProfil

logger = logging.getLogger(__name__)


class InscriptionEventService:
    """
    Service de traitement des événements d'inscription.
    Gère la création des profils étudiants avec credentials.
    """

    async def handle_inscription_soumise(self, payload: Dict[str, Any]) -> None:
        """
        Traite un événement d'inscription soumise.
        
        Payload attendu :
        {
            "inscription_id": "uuid",
            "dossier_id": "uuid",
            "identifiant_national": "20240001",
            "type_profil": "etudiant",
            "annee_academique_id": "uuid",
            "niveau_id": "uuid",
            "filiere_id": "uuid",
            "composante_id": "uuid",
            "valeurs_champs": [{...}],
            "created_at": "2026-03-07T10:30:00Z",
            "created_by": "uuid"
        }
        """
        inscription_id = payload.get("inscription_id")
        identifiant_national = payload.get("identifiant_national")
        type_profil = payload.get("type_profil", "etudiant")

        logger.info(
            f"Événement inscription reçu : "
            f"inscription_id={inscription_id}, "
            f"identifiant_national={identifiant_national}"
        )

        try:
            db = await get_db_session()
            
            try:
                # ── Étape 1 : Vérifier l'existence du profil ──
                profil_repo = ProfilLocalRepository(db)
                profil_existant = await profil_repo.get_by_identifiant_national(
                    identifiant_national
                )

                if profil_existant:
                    # Profil existe déjà → Audit doublon
                    await self._audit_doublon(db, inscription_id, identifiant_national)
                    logger.warning(
                        f"Profil avec identifiant_national={identifiant_national} "
                        f"existe déjà. Inscription ignorée."
                    )
                    await self._publier_erreur(
                        inscription_id=inscription_id,
                        identifiant_national=identifiant_national,
                        erreur_type="DOUBLON_DETECTE",
                        message="Un profil existe déjà pour cet identifiant national"
                    )
                    return

                # ── Étape 2 : Récupérer infos depuis IAM Central ──
                iam_central_data = await self._get_iam_central_data(
                    identifiant_national
                )

                if not iam_central_data:
                    logger.error(
                        f"Impossible de récupérer les données IAM Central "
                        f"pour id_national={identifiant_national}"
                    )
                    await self._publier_erreur(
                        inscription_id=inscription_id,
                        identifiant_national=identifiant_national,
                        erreur_type="IAM_CENTRAL_INDISPO",
                        message="Impossible de récupérer les données depuis IAM Central"
                    )
                    return

                # ── Étape 3 : Créer le profil avec credentials ──
                profil = await self._creer_profil_etudiant(
                    db=db,
                    inscription_id=inscription_id,
                    payload=payload,
                    iam_central_data=iam_central_data,
                    type_profil=type_profil
                )

                # ── Étape 4 : Publier l'événement de succès ──
                await self._publier_succes(
                    inscription_id=inscription_id,
                    profil_id=profil.id,
                    identifiant_national=identifiant_national,
                    iam_central_data=iam_central_data
                )

                logger.info(
                    f"Profil créé avec succès pour "
                    f"id_national={identifiant_national}, "
                    f"profil_id={profil.id}"
                )
                
            finally:
                await db.close()

        except Exception as e:
            logger.error(
                f"Erreur lors du traitement de l'inscription "
                f"{inscription_id}: {str(e)}", exc_info=True
            )
            await self._publier_erreur(
                inscription_id=inscription_id,
                identifiant_national=identifiant_national,
                erreur_type="ERREUR_INTERNE",
                message=f"Erreur interne : {str(e)}"
            )

    async def _audit_doublon(
        self,
        db: AsyncSession,
        inscription_id: str,
        identifiant_national: str
    ) -> None:
        """Enregistre un audit pour doublon détecté."""
        audit_service = AuditService(db)
        await audit_service.log(
            type_action="doublon_inscription_detecte",
            module="iam",
            ressource="profil",
            action="inscription_doublon",
            autorise=True,
            raison=(
                f"Tentative de création d'un profil étudiant déjà existant. "
                f"Inscription: {inscription_id}, ID National: {identifiant_national}"
            ),
        )

    async def _get_iam_central_data(self, identifiant_national: str) -> Optional[Dict[str, Any]]:
        """
        Appelle IAM Central pour récupérer les données complètes de l'utilisateur.
        
        Returns:
            Dict avec id, nom, prenom, email, telephone, etc. ou None si erreur
        """
        # MOCK POUR TEST - Simuler IAM Central
        if identifiant_national in ["20240001", "20240002", "20240003", "20240004", "20240005"]:
            mock_data = {
                "20240001": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "nom": "DUPONT",
                    "prenom": "Jean",
                    "email": "jean.dupont@uob.edu",
                    "telephone": "+22612345678",
                    "identifiant_national": identifiant_national,
                    "statut": "actif"
                },
                "20240002": {
                    "id": "660f9511-f3a7-5278-b827-557766551111",
                    "nom": "MBAYE",
                    "prenom": "Aminata",
                    "email": "aminata.mbaye@uob.edu",
                    "telephone": "+22698765432",
                    "identifiant_national": identifiant_national,
                    "statut": "actif"
                },
                "20240003": {
                    "id": "77110622-a4b8-6389-c938-668877662222",
                    "nom": "TRAORE",
                    "prenom": "Moussa",
                    "email": "moussa.traore@uob.edu",
                    "telephone": "+22655556666",
                    "identifiant_national": identifiant_national,
                    "statut": "actif"
                },
                "20240004": {
                    "id": "88221735-b5c9-7490-da49-779988773333",
                    "nom": "KABORE",
                    "prenom": "Mariam",
                    "email": "mariam.kabore@uob.edu",
                    "telephone": "+22644443333",
                    "identifiant_national": identifiant_national,
                    "statut": "actif"
                },
                "20240005": {
                    "id": "99332846-c6d0-8501-eb50-881199884444",
                    "nom": "OUEDRAOGO",
                    "prenom": "Abdou",
                    "email": "abdou.ouedraogo@uob.edu",
                    "telephone": "+22677772222",
                    "identifiant_national": identifiant_national,
                    "statut": "actif"
                }
            }
            return mock_data.get(identifiant_national)
        
        # Pour les autres IDs, essayer l'appel HTTP réel
        try:
            import httpx
            from app.config import settings

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{settings.IAM_CENTRAL_URL}/api/v1/users/by-id-national",
                    json={
                        "id_national": identifiant_national,
                        "fields_requested": [
                            "id",
                            "nom",
                            "prenom",
                            "email",
                            "telephone",
                            "identifiant_national",
                            "statut"
                        ]
                    },
                    headers={
                        "Authorization": f"Bearer {settings.IAM_CENTRAL_TOKEN}"
                    }
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"IAM Central retourne {response.status_code} "
                        f"pour id_national={identifiant_national}"
                    )
                    return None

        except Exception as e:
            logger.error(
                f"Erreur lors de l'appel à IAM Central : {str(e)}"
            )
            return None

    async def _creer_profil_etudiant(
        self,
        db: AsyncSession,
        inscription_id: str,
        payload: Dict[str, Any],
        iam_central_data: Dict[str, Any],
        type_profil: str
    ):
        """
        Crée le profil étudiant avec credentials temporaires.
        """
        # Générer un username basé sur email + id national
        nom = iam_central_data.get("nom", "").lower().replace(" ", ".")
        prenom = iam_central_data.get("prenom", "").lower().replace(" ", ".")
        id_national = iam_central_data.get("identifiant_national", "")
        username = f"{prenom}.{nom}.{id_national}" if prenom and nom else f"etudiant.{id_national}"

        # Générer un mot de passe temporaire
        import secrets
        temp_password = secrets.token_urlsafe(16)

        # Préparer les données pour création
        create_data = ProfilLocalWithCredentialsCreateSchema(
            user_id_national=UUID(iam_central_data["id"]) if iam_central_data.get("id") else None,
            nom=iam_central_data.get("nom", ""),
            prenom=iam_central_data.get("prenom", ""),
            email=iam_central_data.get("email", ""),
            telephone=iam_central_data.get("telephone"),
            identifiant_national=iam_central_data.get("identifiant_national", ""),
            type_profil=TypeProfil(type_profil),
            username=username,
            password=temp_password,
            require_password_change=True,
            classe=payload.get("classe"),
            niveau=payload.get("niveau"),
            specialite=payload.get("specialite"),
            annee_scolaire=payload.get("annee_scolaire"),
            meta_data={
                "inscription_source": {
                    "inscription_id": inscription_id,
                    "created_at": payload.get("created_at"),
                    "created_by": payload.get("created_by"),
                }
            }
        )

        # Créer via le service
        profil_service = ProfilService(db)
        system_user_id = UUID("00000000-0000-0000-0000-000000000000")  # Système

        profil = await profil_service.creer_avec_credentials(
            data=create_data,
            cree_par=system_user_id,
            request_id=inscription_id
        )

        return profil

    async def _publier_succes(
        self,
        inscription_id: str,
        profil_id: str,
        identifiant_national: str,
        iam_central_data: Dict[str, Any]
    ) -> None:
        """Publie un événement de succès."""
        producer = KafkaProducer()
        
        await producer.publish(
            topic=Topics.IAM_PROFIL_CREE,
            payload={
                "event": "profil_etudiant_cree_depuis_inscription",
                "inscription_id": inscription_id,
                "profil_id": str(profil_id),
                "user_id_national": str(iam_central_data.get("id")),
                "identifiant_national": identifiant_national,
                "nom": iam_central_data.get("nom"),
                "prenom": iam_central_data.get("prenom"),
                "email": iam_central_data.get("email"),
                "type_profil": "etudiant",
                "status": "SUCCESS",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            key=str(profil_id)
        )

    async def _publier_erreur(
        self,
        inscription_id: str,
        identifiant_national: str,
        erreur_type: str,
        message: str
    ) -> None:
        """Publie un événement d'erreur."""
        producer = KafkaProducer()

        await producer.publish(
            topic=Topics.IAM_PROFIL_ERREUR,
            payload={
                "event": "profil_etudiant_erreur",
                "inscription_id": inscription_id,
                "identifiant_national": identifiant_national,
                "erreur_type": erreur_type,
                "message": message,
                "status": "ERROR",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            key=identifiant_national
        )
