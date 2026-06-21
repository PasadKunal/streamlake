"""
Data ingestion endpoints for StreamLake.

Accepts external order data via webhook or CSV and writes directly to
the Bronze Delta table in S3, bypassing Kafka (no cloud Kafka required).

Endpoints:
  POST /ingest/webhook?source=shopify       — single Shopify order webhook
  POST /ingest/webhook?source=woocommerce   — single WooCommerce order webhook
  POST /ingest/csv                          — CSV file of historical orders

After ingestion, the downstream pipeline (bronze_to_silver -> run_gold_pipeline
-> feature_pipeline) must run to propagate records through the lakehouse.
"""
from __future__ import annotations

import io
import os

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from ingestion.normalizers import (
    normalize_csv_row,
    normalize_shopify_order,
    normalize_woocommerce_order,
)
from serving.auth import get_tenant
from storage.bronze_schema import BRONZE_SCHEMA
from storage.delta_writer import write_batch

router = APIRouter(prefix="/ingest", tags=["ingestion"])

BRONZE_PATH = os.getenv("DELTA_BRONZE_PATH", "s3://streamlake-bronze/events")
_SUPPORTED_SOURCES = {"shopify", "woocommerce"}


class WebhookResponse(BaseModel):
    status: str
    event_id: str
    user_id: str
    amount_cents: int
    source: str
    tenant: str


class CsvResponse(BaseModel):
    status: str
    rows_ingested: int
    rows_failed: int
    errors: list[dict]
    tenant: str
    pipeline_note: str


@router.post("/webhook", response_model=WebhookResponse)
async def webhook_ingest(
    request: Request,
    source: str = Query("shopify", description="Platform sending the webhook: shopify | woocommerce"),
    tenant: str = Depends(get_tenant),
) -> WebhookResponse:
    """
    Accept a single order webhook from Shopify or WooCommerce and write it
    to the Bronze Delta table in S3.
    """
    if source not in _SUPPORTED_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source {source!r}. Supported: {sorted(_SUPPORTED_SOURCES)}",
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON")

    try:
        if source == "shopify":
            record = normalize_shopify_order(payload)
        else:
            record = normalize_woocommerce_order(payload)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"Payload normalization failed: {e}")

    table_path = f"{BRONZE_PATH}/{tenant}"
    try:
        write_batch([record], table_path, BRONZE_SCHEMA, partition_by=["ingestion_date"])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Bronze write failed: {e}")

    return WebhookResponse(
        status="accepted",
        event_id=record["event_id"],
        user_id=record["user_id"],
        amount_cents=record["amount_cents"],
        source=source,
        tenant=tenant,
    )


@router.post("/csv", response_model=CsvResponse)
async def csv_ingest(
    file: UploadFile = File(...),
    tenant: str = Depends(get_tenant),
) -> CsvResponse:
    """
    Accept a CSV file of historical orders and write all valid rows to the
    Bronze Delta table in S3.

    Required columns (any alias accepted):
      order_id, customer_id, total_amount

    Optional columns:
      order_date, product_id, country
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    content = await file.read()
    try:
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV is empty")

    records: list[dict] = []
    errors:  list[dict] = []

    for i, row in df.iterrows():
        try:
            records.append(normalize_csv_row(row.to_dict()))
        except (KeyError, ValueError) as e:
            errors.append({"row": int(i) + 2, "error": str(e)})  # +2 = header + 1-indexed

    if not records:
        raise HTTPException(
            status_code=422,
            detail={"message": "No valid rows found", "errors": errors},
        )

    table_path = f"{BRONZE_PATH}/{tenant}"
    try:
        written = write_batch(records, table_path, BRONZE_SCHEMA, partition_by=["ingestion_date"])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Bronze write failed: {e}")

    return CsvResponse(
        status="accepted",
        rows_ingested=written,
        rows_failed=len(errors),
        errors=errors,
        tenant=tenant,
        pipeline_note=(
            "Records written to Bronze Delta (S3). Run processing.bronze_to_silver, "
            "run_gold_pipeline, and feature_store.feature_pipeline to propagate "
            "through the lakehouse and update the online feature store."
        ),
    )
