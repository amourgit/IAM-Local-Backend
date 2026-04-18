import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any
from confluent_kafka import Producer
from app.config import settings

logger = logging.getLogger(__name__)


class KafkaProducer:

    _instance: Producer | None = None

    def _get_producer(self) -> Producer:
        if self._instance is None:
            self.__class__._instance = Producer({
                "bootstrap.servers" : settings.KAFKA_BOOTSTRAP_SERVERS,
                "client.id"         : "module-02-iam-local",
                "acks"              : "all",
                "retries"           : 3,
                "retry.backoff.ms"  : 300,
            })
        return self.__class__._instance

    async def publish(
        self,
        topic   : str,
        payload : dict[str, Any],
        key     : str | None = None,
    ) -> None:
        """
        Publie un message Kafka enveloppé dans une enveloppe standard.
        Utilisé par la majorité des services.
        """
        producer = self._get_producer()
        message = {
            "event_id"  : str(uuid.uuid4()),
            "event_type": topic,
            "service"   : "module-02-iam-local",
            "timestamp" : datetime.now(timezone.utc).isoformat(),
            "payload"   : payload,
        }
        try:
            producer.produce(
                topic    = topic,
                key      = key or payload.get("profil_id", ""),
                value    = json.dumps(message, default=str),
                callback = self._delivery_report,
            )
            producer.poll(0)
        except Exception as e:
            logger.error(
                f"Kafka publish failed — topic={topic} error={e}"
            )

    async def send_message(
        self,
        topic : str,
        value : dict[str, Any],
        key   : str | None = None,
    ) -> None:
        """
        ✅ Alias de publish() pour les appels utilisant send_message().
        Reçoit value= au lieu de payload= — les deux styles sont supportés.
        """
        await self.publish(topic=topic, payload=value, key=key)

    def flush(self) -> None:
        self._get_producer().flush(timeout=5)

    @staticmethod
    def _delivery_report(err, msg) -> None:
        if err:
            logger.error(
                f"Kafka delivery failed — "
                f"topic={msg.topic()} error={err}"
            )
        else:
            logger.debug(
                f"Kafka delivered — "
                f"topic={msg.topic()} "
                f"partition={msg.partition()} "
                f"offset={msg.offset()}"
            )