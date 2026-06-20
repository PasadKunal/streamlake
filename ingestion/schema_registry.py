"""
Schema Registry utilities for StreamLake.
Handles schema registration and serializer/deserializer creation.
"""
import os
from pathlib import Path

from confluent_kafka.schema_registry import Schema, SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from loguru import logger

SCHEMA_DIR = Path(__file__).parent / "avro_schemas"
USER_EVENT_SCHEMA_PATH = SCHEMA_DIR / "user_event.avsc"

# Confluent convention: {topic}-value
USER_EVENT_SUBJECT = "streamlake.events.raw-value"


def get_kafka_sasl_config() -> dict:
    """Return SASL_SSL config when KAFKA_SASL_USERNAME/PASSWORD are set (Redpanda Cloud)."""
    username = os.getenv("KAFKA_SASL_USERNAME")
    password = os.getenv("KAFKA_SASL_PASSWORD")
    if username and password:
        return {
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms":   "SCRAM-SHA-256",
            "sasl.username":     username,
            "sasl.password":     password,
        }
    return {}


def get_client(url: str) -> SchemaRegistryClient:
    config: dict = {"url": url}
    api_key    = os.getenv("SCHEMA_REGISTRY_API_KEY")
    api_secret = os.getenv("SCHEMA_REGISTRY_API_SECRET")
    if api_key and api_secret:
        config["basic.auth.credentials.source"] = "USER_INFO"
        config["basic.auth.user.info"]           = f"{api_key}:{api_secret}"
    return SchemaRegistryClient(config)


def register_schema(client: SchemaRegistryClient, subject: str, schema_path: Path) -> int:
    """Register an Avro schema and return its schema ID."""
    schema_str = schema_path.read_text()
    schema = Schema(schema_str, schema_type="AVRO")
    schema_id = client.register_schema(subject, schema)
    logger.info(f"Registered schema '{subject}' → schema_id={schema_id}")
    return schema_id


def get_avro_serializer(client: SchemaRegistryClient, schema_str: str) -> AvroSerializer:
    """Return an AvroSerializer that passes dict objects through unchanged."""
    return AvroSerializer(client, schema_str, lambda obj, ctx: obj)


def get_avro_deserializer(client: SchemaRegistryClient) -> AvroDeserializer:
    """Return an AvroDeserializer that yields plain dicts."""
    return AvroDeserializer(client, schema_str=None, from_dict=lambda obj, ctx: obj)


def register_all_schemas(registry_url: str) -> dict[str, int]:
    """Register all StreamLake Avro schemas on startup."""
    client = get_client(registry_url)
    registered: dict[str, int] = {}

    schema_id = register_schema(client, USER_EVENT_SUBJECT, USER_EVENT_SCHEMA_PATH)
    registered[USER_EVENT_SUBJECT] = schema_id

    return registered
