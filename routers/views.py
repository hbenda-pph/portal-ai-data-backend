from typing import Any

from fastapi import APIRouter, HTTPException, Path

from database import is_authorized_tenant_async, query_gold_view_async

router = APIRouter(tags=["views"])


async def _read_gold_view(tenant_id: str, view_name: str) -> list[dict[str, Any]]:
    if not await is_authorized_tenant_async(tenant_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        return await query_gold_view_async(tenant_id, view_name, limit=100)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Error al consultar BigQuery.",
        ) from exc


@router.get("/call-intelligence/{tenant_id}")
async def get_call_intelligence(
    tenant_id: str = Path(..., min_length=6, max_length=30),
) -> list[dict[str, Any]]:
    """Lee `{tenant}.gold.vw_call_intelligence` tras validar el tenant."""
    return await _read_gold_view(tenant_id, "vw_call_intelligence")


@router.get("/csr-performance-coaching/{tenant_id}")
async def get_csr_performance_coaching(
    tenant_id: str = Path(..., min_length=6, max_length=30),
) -> list[dict[str, Any]]:
    """Lee `{tenant}.gold.vw_csr_performance_coaching` tras validar el tenant."""
    return await _read_gold_view(tenant_id, "vw_csr_performance_coaching")
