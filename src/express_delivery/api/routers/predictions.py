from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from express_delivery.api.dependencies import get_order_service, get_prediction_service
from express_delivery.api.schemas import Error, OrderFeatures, Prediction
from express_delivery.services.order_service import OrderService
from express_delivery.services.prediction_service import PredictionService

router = APIRouter(prefix="/v1/predictions", tags=["predictions"])


@router.post(
    "",
    operation_id="createPrediction",
    summary="Prédire l'éligibilité express d'une commande",
    response_model=Prediction,
    responses={
        422: {"model": Error, "description": "Commande invalide"},
        503: {"model": Error, "description": "Modèle indisponible"},
    },
)
def create_prediction(
    order: OrderFeatures,
    predictor: PredictionService = Depends(get_prediction_service),
    orders: OrderService = Depends(get_order_service),
) -> Prediction:
    """Prédiction synchrone : implémentation HTTP de la cellule 34 du notebook."""
    result = predictor.predict(orders.resolve_id(order.order_id), order.model_features())
    return Prediction(**asdict(result))
