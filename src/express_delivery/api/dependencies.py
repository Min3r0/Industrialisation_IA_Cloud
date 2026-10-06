"""Accès aux services depuis les routes (injection de dépendances FastAPI)."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from express_delivery.abstractions.order_store import OrderStore
from express_delivery.api.errors import ApiError
from express_delivery.services.order_service import OrderService
from express_delivery.services.prediction_service import PredictionService


@dataclass
class Container:
    """Services assemblés au démarrage (composition root : voir app.create_app)."""

    order_store: OrderStore
    order_service: OrderService
    prediction_service: PredictionService | None  # None si le modèle n'a pas pu être chargé


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_order_service(request: Request) -> OrderService:
    return get_container(request).order_service


def get_prediction_service(request: Request) -> PredictionService:
    service = get_container(request).prediction_service
    if service is None:
        raise ApiError(503, "model_unavailable", "Le modèle n'est pas chargé.")
    return service
