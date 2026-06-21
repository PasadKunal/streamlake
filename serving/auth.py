"""
API key authentication for StreamLake.

Configure via API_KEYS env var (JSON object mapping key -> tenant_id):
  API_KEYS={"sk-demo-streamlake": "tenant_demo", "sk-acme-abc123": "tenant_acme"}

If API_KEYS is not set, the default demo key "sk-demo-streamlake" is accepted
and resolves to tenant "tenant_demo".
"""
from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()

_raw = os.getenv("API_KEYS", '{"sk-demo-streamlake": "tenant_demo"}')
_API_KEYS: dict[str, str] = json.loads(_raw)


def get_tenant(x_api_key: str = Header(...)) -> str:
    """FastAPI dependency: validates X-Api-Key header, returns tenant_id."""
    tenant = _API_KEYS.get(x_api_key)
    if not tenant:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return tenant


def configured_tenants() -> list[str]:
    return sorted(set(_API_KEYS.values()))
