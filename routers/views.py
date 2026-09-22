from typing import Any

from fastapi import APIRouter, HTTPException, Path

from database import is_authorized_tenant_async, query_gold_view_async

router = APIRouter(tags=["views"])


@router.get("/call-intelligence/{tenant_id}")
async def get_call_intelligence(
    tenant_id: str = Path(..., min_length=6, max_length=30),
) -> list[dict[str, Any]]:
    """Lee `{tenant}.gold.vw_call_intelligence` tras validar el tenant."""
    if not await is_authorized_tenant_async(tenant_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        return await query_gold_view_async(
            tenant_id, "vw_call_intelligence", limit=100
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Error al consultar BigQuery.",
        ) from exc
