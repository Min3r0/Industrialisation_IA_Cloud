from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from express_delivery.api.dependencies import get_order_service
from express_delivery.api.errors import ApiError
from express_delivery.api.schemas import Error, OrderAccepted, OrderFeatures
from express_delivery.services.order_service import OrderService

router = APIRouter(prefix="/v1/orders", tags=["orders"])


@router.post(
    "",
    operation_id="createOrder",
    summary="Enregistrer une commande à prédire",
    status_code=202,
    response_model=OrderAccepted,
    responses={422: {"model": Error}, 500: {"model": Error}},
)
def create_order(order: OrderFeatures, service: OrderService = Depends(get_order_service)) -> OrderAccepted:
    """La commande est persistée via l'OrderStore ; la prédiction sera asynchrone (séance 5)."""
    saved = service.register(order.order_id, order.model_features())
    return OrderAccepted(order_id=saved.order_id)


@router.get(
    "/{order_id}",
    operation_id="getOrder",
    summary="Relire une commande collectée",
    response_model=OrderFeatures,
    response_model_exclude_none=True,
    responses={404: {"model": Error, "description": "Commande inconnue"}},
)
def get_order(
    order_id: str = Path(examples=["CMD-000001"]),
    service: OrderService = Depends(get_order_service),
) -> OrderFeatures:
    order = service.get(order_id)
    if order is None:
        raise ApiError(404, "order_not_found", f"Commande inconnue : {order_id}")
    return OrderFeatures(order_id=order.order_id, **order.features)
