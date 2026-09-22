from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import authorized_tenants_async

router = APIRouter(tags=["tenants"])


class TenantsResponse(BaseModel):
    tenants: list[str] = Field(
        description="Proyectos GCP autorizados (company_project_id)."
    )


@router.get("/tenants", response_model=TenantsResponse)
async def list_tenants() -> TenantsResponse:
    """Lista de proyectos válidos para alimentar el selector del frontend."""
    try:
        tenants = await authorized_tenants_async()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="No se pudo cargar el catálogo de tenants.",
        ) from exc
    return TenantsResponse(tenants=sorted(tenants))
