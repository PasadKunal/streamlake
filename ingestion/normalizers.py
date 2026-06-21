"""
Normalizers for external event formats -> Bronze Delta schema.

Supported sources:
  - Shopify orders/create webhook
  - WooCommerce order.created webhook
  - Generic CSV (flexible column aliases)

All produce records matching BRONZE_SCHEMA in storage/bronze_schema.py.
Kafka metadata fields are filled with source-specific placeholders since
these events arrive via HTTP, not Kafka.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_ts(value: Any) -> int:
    """Parse an ISO timestamp string or numeric epoch to milliseconds."""
    if value is None:
        return _now_ms()
    if isinstance(value, (int, float)):
        # Assume seconds if plausibly in epoch-seconds range
        v = float(value)
        return int(v * 1000) if v < 1e12 else int(v)
    from dateutil.parser import parse as dtparse
    dt = dtparse(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _find(row: dict, *keys: str) -> Any:
    """Return the first matching value from a dict, case-insensitive."""
    lower = {k.lower(): v for k, v in row.items()}
    for k in keys:
        if k.lower() in lower:
            return lower[k.lower()]
    return None


# ── Shopify ───────────────────────────────────────────────────────────────────

def normalize_shopify_order(payload: dict) -> dict:
    """
    Map a Shopify orders/create webhook payload to the Bronze event schema.
    Required fields: id, created_at, customer.id or customer_id, total_price.
    """
    order_id = payload.get("id")
    if not order_id:
        raise ValueError("Missing 'id' in Shopify payload")

    customer = payload.get("customer") or {}
    customer_id = customer.get("id") or payload.get("customer_id")
    if not customer_id:
        raise ValueError("Missing customer id in Shopify payload")

    created_at = payload.get("created_at")
    if not created_at:
        raise ValueError("Missing 'created_at' in Shopify payload")

    total = payload.get("total_price") or payload.get("subtotal_price", "0")
    line_items = payload.get("line_items") or []
    product_id = str(line_items[0]["product_id"]) if line_items else None

    billing = payload.get("billing_address") or payload.get("shipping_address") or {}
    country = (billing.get("country_code") or billing.get("country") or "US")[:2].upper()

    return {
        "event_id":               f"shopify-{order_id}",
        "event_type":             "purchase",
        "user_id":                f"USER-SHOPIFY-{customer_id}",
        "session_id":             str(uuid.uuid4()),
        "timestamp_ms":           _parse_ts(created_at),
        "page_url":               payload.get("landing_site"),
        "product_id":             product_id,
        "amount_cents":           int(float(total) * 100),
        "device_type":            "web",
        "country_code":           country,
        "app_version":            "shopify-webhook-v1",
        "kafka_topic":            "webhook.shopify",
        "kafka_partition":        0,
        "kafka_offset":           0,
        "ingestion_timestamp_ms": _now_ms(),
        "ingestion_date":         _today_utc(),
    }


# ── WooCommerce ───────────────────────────────────────────────────────────────

def normalize_woocommerce_order(payload: dict) -> dict:
    """
    Map a WooCommerce order.created webhook payload to the Bronze event schema.
    Required fields: id, date_created, customer_id, total.
    """
    order_id = payload.get("id")
    if not order_id:
        raise ValueError("Missing 'id' in WooCommerce payload")

    customer_id = payload.get("customer_id")
    if not customer_id:
        raise ValueError("Missing 'customer_id' in WooCommerce payload")

    created_at = payload.get("date_created") or payload.get("date_created_gmt")
    if not created_at:
        raise ValueError("Missing 'date_created' in WooCommerce payload")

    total = payload.get("total", "0")
    line_items = payload.get("line_items") or []
    product_id = str(line_items[0]["product_id"]) if line_items else None

    billing = payload.get("billing") or {}
    country = (billing.get("country") or "US")[:2].upper()

    return {
        "event_id":               f"woo-{order_id}",
        "event_type":             "purchase",
        "user_id":                f"USER-WOO-{customer_id}",
        "session_id":             str(uuid.uuid4()),
        "timestamp_ms":           _parse_ts(created_at),
        "page_url":               None,
        "product_id":             product_id,
        "amount_cents":           int(float(total) * 100),
        "device_type":            "web",
        "country_code":           country,
        "app_version":            "woocommerce-webhook-v1",
        "kafka_topic":            "webhook.woocommerce",
        "kafka_partition":        0,
        "kafka_offset":           0,
        "ingestion_timestamp_ms": _now_ms(),
        "ingestion_date":         _today_utc(),
    }


# ── Generic CSV ───────────────────────────────────────────────────────────────

_ORDER_ID_KEYS    = ("order_id", "id", "order_number", "order")
_CUSTOMER_ID_KEYS = ("customer_id", "user_id", "customer", "client_id", "email")
_DATE_KEYS        = ("order_date", "created_at", "date", "timestamp", "purchase_date")
_AMOUNT_KEYS      = ("total_amount", "total", "amount", "revenue", "price", "order_total")
_PRODUCT_KEYS     = ("product_id", "item_id", "sku")
_COUNTRY_KEYS     = ("country", "country_code", "billing_country", "ship_country")


def normalize_csv_row(row: dict) -> dict:
    """
    Map a CSV row with flexible column names to the Bronze event schema.
    Required columns (any alias): order_id, customer_id, total_amount.
    Optional: order_date, product_id, country.
    """
    order_id    = _find(row, *_ORDER_ID_KEYS)
    customer_id = _find(row, *_CUSTOMER_ID_KEYS)
    total       = _find(row, *_AMOUNT_KEYS)

    if order_id is None:
        raise ValueError(f"No order_id column found. Expected one of: {_ORDER_ID_KEYS}")
    if customer_id is None:
        raise ValueError(f"No customer_id column found. Expected one of: {_CUSTOMER_ID_KEYS}")
    if total is None:
        raise ValueError(f"No amount column found. Expected one of: {_AMOUNT_KEYS}")

    date_val   = _find(row, *_DATE_KEYS)
    product_id = _find(row, *_PRODUCT_KEYS)
    country    = (_find(row, *_COUNTRY_KEYS) or "US")
    country    = str(country)[:2].upper()

    return {
        "event_id":               f"csv-{order_id}",
        "event_type":             "purchase",
        "user_id":                f"USER-{customer_id}",
        "session_id":             str(uuid.uuid4()),
        "timestamp_ms":           _parse_ts(date_val),
        "page_url":               None,
        "product_id":             str(product_id) if product_id else None,
        "amount_cents":           int(float(str(total).replace(",", "").replace("$", "")) * 100),
        "device_type":            "web",
        "country_code":           country,
        "app_version":            "csv-upload-v1",
        "kafka_topic":            "csv_upload",
        "kafka_partition":        0,
        "kafka_offset":           0,
        "ingestion_timestamp_ms": _now_ms(),
        "ingestion_date":         _today_utc(),
    }
