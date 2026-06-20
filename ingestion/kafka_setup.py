"""
One-time Kafka topic setup script.
Run this once before starting the producer or consumer.

Usage:
    python -m ingestion.kafka_setup
"""
import os

from confluent_kafka.admin import AdminClient, NewTopic
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

TOPICS = [
    NewTopic(
        topic=os.getenv("KAFKA_TOPIC_EVENTS", "streamlake.events.raw"),
        num_partitions=4,
        replication_factor=1,
        config={
            "retention.ms": str(7 * 24 * 60 * 60 * 1000),  # 7 days
            "cleanup.policy": "delete",
            "compression.type": "lz4",
        },
    )
]


def create_topics(bootstrap_servers: str) -> None:
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    result = admin.create_topics(TOPICS)

    for topic, future in result.items():
        try:
            future.result()
            logger.info(f"Topic '{topic}' created successfully")
        except Exception as e:
            if "TOPIC_ALREADY_EXISTS" in str(e):
                logger.info(f"Topic '{topic}' already exists — skipping")
            else:
                logger.error(f"Failed to create topic '{topic}': {e}")
                raise


if __name__ == "__main__":
    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    logger.info(f"Connecting to Kafka at {servers}")
    create_topics(servers)
