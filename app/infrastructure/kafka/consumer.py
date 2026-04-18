import json
import asyncio
import logging
from app.config import settings
from app.infrastructure.kafka.topics import Topics

logger = logging.getLogger(__name__)


class KafkaConsumer:
    """
    Consommateur Kafka du Module 02 — IAM Local.
    Topics consommés :
    - scolarite.inscription.soumise     → création profil étudiant
    - iam.registration.permissions      → enregistrement permissions externes
    - iam.registration.endpoints        → enregistrement endpoints externes
    """

    def __init__(self):
        self._running  = False
        self._consumer = None

    def _get_consumer(self):
        if self._consumer is None:
            try:
                from confluent_kafka import Consumer
                self._consumer = Consumer({
                    "bootstrap.servers"  : settings.KAFKA_BOOTSTRAP_SERVERS,
                    "group.id"           : "module-02-iam-local-group",
                    "auto.offset.reset"  : "earliest",
                    "enable.auto.commit" : True,
                })
                self._consumer.subscribe([
                    Topics.SCOLARITE_INSCRIPTION_SOUMISE,
                    Topics.IAM_REGISTRATION_PERMISSIONS,
                    Topics.IAM_REGISTRATION_ENDPOINTS,
                ])
                logger.info(
                    "Kafka consumer initialisé — topics: "
                    f"{Topics.SCOLARITE_INSCRIPTION_SOUMISE}, "
                    f"{Topics.IAM_REGISTRATION_PERMISSIONS}, "
                    f"{Topics.IAM_REGISTRATION_ENDPOINTS}"
                )
            except Exception as e:
                logger.warning(f"Kafka consumer non disponible : {e}. Mode dégradé.")
                self._consumer = None
        return self._consumer

    async def start(self) -> None:
        self._running = True
        consumer = self._get_consumer()
        if not consumer:
            logger.warning("Kafka consumer non démarré — mode dégradé.")
            return

        logger.info("Kafka consumer démarré pour IAM Local.")
        while self._running:
            try:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    await asyncio.sleep(0.1)
                    continue
                if msg.error():
                    logger.error(f"Kafka consumer error : {msg.error()}")
                    continue

                topic = msg.topic()

                if not msg.value() or msg.value().decode("utf-8").strip() == "":
                    logger.warning(f"Message vide sur topic {topic} — ignoré")
                    continue

                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                except json.JSONDecodeError as e:
                    logger.error(
                        f"JSON invalide sur {topic}: "
                        f"{msg.value().decode('utf-8')[:100]} — {e}"
                    )
                    continue

                await self._dispatch(topic, payload)

            except Exception as e:
                logger.error(f"Kafka consumer loop error : {e}")
                await asyncio.sleep(1.0)

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            self._consumer.close()
            logger.info("Kafka consumer arrêté.")

    async def _dispatch(self, topic: str, message: dict) -> None:
        """Route le message vers le handler approprié."""

        # ── Inscriptions étudiants ────────────────────────────────
        if topic == Topics.SCOLARITE_INSCRIPTION_SOUMISE:
            from app.services.inscription_event_service import InscriptionEventService
            service = InscriptionEventService()
            await service.handle_inscription_soumise(message.get("payload", {}))

        # ── Enregistrement permissions externes ───────────────────
        elif topic == Topics.IAM_REGISTRATION_PERMISSIONS:
            from app.services.permission_registration_service import PermissionRegistrationService
            service = PermissionRegistrationService()
            await service.handle_registration(message)

        # ── Enregistrement endpoints externes ─────────────────────
        elif topic == Topics.IAM_REGISTRATION_ENDPOINTS:
            from app.services.endpoint_registration_service import EndpointRegistrationService
            service = EndpointRegistrationService()
            await service.handle_registration(message)

        else:
            logger.warning(f"Topic non géré: {topic}")
