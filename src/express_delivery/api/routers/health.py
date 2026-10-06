from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from express_delivery import SERVICE_NAME, __version__
from express_delivery.api.dependencies import Container, get_container
from express_delivery.api.schemas import HealthStatus, ReadinessStatus

router = APIRouter(tags=["health"])


@router.get("/health", operation_id="getHealth", summary="Sonde de vivacité",
            response_model=HealthStatus)
def get_health() -> HealthStatus:
    """Répond 200 si le processus est vivant. Ne dépend d'aucune brique externe."""
    return HealthStatus(service=SERVICE_NAME, version=__version__)


@router.get(
    "/health/ready",
    operation_id="getReadiness",
    summary="Sonde de disponibilité",
    response_model=ReadinessStatus,
    responses={503: {"model": ReadinessStatus, "description": "Le service n'est pas prêt"}},
)
def get_readiness(container: Container = Depends(get_container)) -> JSONResponse:
    model_ok = container.prediction_service is not None
    store_ok = container.order_store.is_reachable()
    status = ReadinessStatus(
        status="ready" if model_ok and store_ok else "not_ready",
        checks={
            "model": "loaded" if model_ok else "not_loaded",
            "order_store": "reachable" if store_ok else "unreachable",
        },
        version=container.prediction_service.model_version if model_ok else None,
    )
    return JSONResponse(
        status_code=200 if status.status == "ready" else 503,
        content=status.model_dump(exclude_none=True),
    )
