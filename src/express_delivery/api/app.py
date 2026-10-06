"""Composition root : seul endroit qui connaît les implémentations concrètes."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from express_delivery import SERVICE_NAME, __version__
from express_delivery.abstractions.model_repository import ModelNotFoundError, ModelRepository
from express_delivery.abstractions.order_store import OrderStore
from express_delivery.api.dependencies import Container
from express_delivery.api.errors import register_error_handlers
from express_delivery.api.openapi import install_contract_openapi
from express_delivery.api.routers import health, orders, predictions
from express_delivery.config import Settings
from express_delivery.infrastructure.filesystem.model_repository import FileModelRepository
from express_delivery.infrastructure.sqlite.order_store import SqliteOrderStore
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
        )
        yield

    app = FastAPI(
        title=f"{SERVICE_NAME} API",
        version=__version__,
        description="API de prédiction d'éligibilité à la livraison express.",
        lifespan=lifespan,
    )
    register_error_handlers(app)
    for router in (health.router, orders.router, predictions.router):
        app.include_router(router)
    install_contract_openapi(app)
    return app
