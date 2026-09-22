"""Cliente BigQuery singleton y caché de tenants autorizados."""

from __future__ import annotations

import asyncio
import os
import re
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any

from google.cloud import bigquery

# Jobs de BigQuery en el proyecto de compute; los datos viven en pph-central / tenants.
BQ_JOB_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "platform-partners-des")
TENANTS_QUERY = "SELECT company_project_id FROM `pph-central.settings.companies`"

# IDs de proyecto GCP: 6–30 chars, empiezan con letra, minúsculas/dígitos/guiones.
GCP_PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


@lru_cache(maxsize=1)
def get_bq_client() -> bigquery.Client:
    """Singleton del cliente BigQuery (ADC). Los jobs corren en platform-partners-des."""
    return bigquery.Client(project=BQ_JOB_PROJECT)


def _load_authorized_tenants() -> frozenset[str]:
    client = get_bq_client()
    rows = client.query(TENANTS_QUERY).result()
    return frozenset(
        str(row.company_project_id)
        for row in rows
        if row.company_project_id
    )


@lru_cache(maxsize=1)
def get_authorized_tenants() -> frozenset[str]:
    """Caché en memoria de `company_project_id` válidos.

    Temporal: `@lru_cache` no expira. Sustituir por TTL en producción.
    """
    return _load_authorized_tenants()


def clear_tenant_cache() -> None:
    get_authorized_tenants.cache_clear()


def is_valid_project_id(tenant_id: str) -> bool:
    return bool(GCP_PROJECT_ID_RE.fullmatch(tenant_id))


def is_authorized_tenant(tenant_id: str) -> bool:
    """True solo si el id pasa el formato GCP y está en la lista maestra."""
    if not is_valid_project_id(tenant_id):
        return False
    return tenant_id in get_authorized_tenants()


async def authorized_tenants_async() -> frozenset[str]:
    return await asyncio.to_thread(get_authorized_tenants)


async def is_authorized_tenant_async(tenant_id: str) -> bool:
    if not is_valid_project_id(tenant_id):
        return False
    tenants = await authorized_tenants_async()
    return tenant_id in tenants


def serialize_bq_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (list, tuple)):
        return [serialize_bq_value(item) for item in value]
    if isinstance(value, dict):
        return {k: serialize_bq_value(v) for k, v in value.items()}
    return value


def rows_to_dicts(rows: Any) -> list[dict[str, Any]]:
    return [
        {key: serialize_bq_value(value) for key, value in dict(row).items()}
        for row in rows
    ]


def query_gold_view(tenant_id: str, view_name: str, limit: int = 100) -> list[dict[str, Any]]:
    """Consulta una vista Gold. `tenant_id` DEBE estar pre-validado."""
    if not is_authorized_tenant(tenant_id):
        raise PermissionError(f"Tenant no autorizado: {tenant_id}")

    # Vista allowlisted: nunca interpolar nombres de vista desde el cliente.
    allowed_views = {
        "vw_call_intelligence",
        "vw_csr_performance",
        "vw_lost_opportunity",
        "vw_service_benchmarks",
    }
    if view_name not in allowed_views:
        raise ValueError(f"Vista no permitida: {view_name}")
    if not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit inválido")

    sql = f"SELECT * FROM `{tenant_id}.gold.{view_name}` LIMIT {limit}"
    job = get_bq_client().query(sql)
    return rows_to_dicts(job.result())


async def query_gold_view_async(
    tenant_id: str, view_name: str, limit: int = 100
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(query_gold_view, tenant_id, view_name, limit)
