"""Composition root : seul endroit qui connaît les implémentations concrètes."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from express_delivery import SERVICE_NAME, __version__
from express_delivery.abstractions.model_repository import ModelNotFoundError, ModelRepository
from express_delivery.abstractions.order_store import OrderStore
from express_delivery.api.dependencies import Container
from express_delivery.api.errors import register_error_handlers
from express_delivery.api.openapi import install_contract_openapi
from express_delivery.api.routers import health, orders, predictions
from express_delivery.api.security import require_role
from express_delivery.config import Settings
from express_delivery.domain.security import Role
from express_delivery.infrastructure.env.api_key_store import EnvApiKeyStore
from express_delivery.infrastructure.filesystem.model_repository import FileModelRepository
from express_delivery.infrastructure.memory.rate_limiter import SlidingWindowRateLimiter
from express_delivery.infrastructure.sqlite.order_store import SqliteOrderStore
from express_delivery.services.auth_service import AuthService
from express_delivery.services.order_service import OrderService
from express_delivery.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)


def _build_prediction_service(
    repository: ModelRepository, settings: Settings
) -> PredictionService | None:
    try:
        model = repository.load(settings.model_version)
    except ModelNotFoundError as error:
        # Le processus démarre quand même : /health répond, /health/ready renvoie 503.
        logger.error("Modèle non chargé : %s", error)
        return None
    return PredictionService(model, settings.prediction_threshold)


def _build_auth_service(settings: Settings) -> AuthService | None:
    if not settings.auth_enabled:
        logger.warning("Authentification désactivée (AUTH_ENABLED=false) : réservé au dev.")
        return None
    return AuthService(EnvApiKeyStore(settings.api_keys))


def create_app(
    settings: Settings | None = None,
    order_store: OrderStore | None = None,
    model_repository: ModelRepository | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = order_store or SqliteOrderStore(settings.database_path)
        repository = model_repository or FileModelRepository(settings.models_dir)
        app.state.container = Container(
            order_store=store,
            order_service=OrderService(store),
            prediction_service=_build_prediction_service(repository, settings),
            rate_limiter=SlidingWindowRateLimiter(settings.rate_limit_per_minute),
            auth_service=_build_auth_service(settings),
        )
        yield

    app = FastAPI(
        title=f"{SERVICE_NAME} API",
        version=__version__,
        description="API de prédiction d'éligibilité à la livraison express.",
        lifespan=lifespan,
        # Pas de documentation interactive exposée en production (ADR-0005)
        docs_url="/docs" if settings.expose_docs else None,
        redoc_url="/redoc" if settings.expose_docs else None,
        openapi_url="/openapi.json" if settings.expose_docs else None,
    )
    register_error_handlers(app)
    app.include_router(health.router)  # sondes publiques : appelées par l'orchestrateur
    protected = [Depends(require_role(Role.USER))]
    for router in (orders.router, predictions.router):
        app.include_router(router, dependencies=protected)
    install_contract_openapi(app)
    return app
