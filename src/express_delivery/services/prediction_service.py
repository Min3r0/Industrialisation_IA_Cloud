"""Cas d'usage « prédire l'éligibilité d'une commande » (cellule 34 du notebook)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from express_delivery.abstractions.model_repository import LoadedModel
from express_delivery.domain.models import PredictionResult


class PredictionService:
    def __init__(self, model: LoadedModel, threshold: float) -> None:
        self._model = model
        self._threshold = threshold

    @property
    def model_version(self) -> str:
        return self._model.metadata.model_version

    def predict(self, order_id: str, features: Mapping[str, Any]) -> PredictionResult:
        start = time.perf_counter()
        columns = list(self._model.metadata.features)
        frame = pd.DataFrame([{name: features[name] for name in columns}], columns=columns)
        probability = float(self._model.estimator.predict_proba(frame)[0, 1])
        eligible = probability >= self._threshold
        return PredictionResult(
            order_id=order_id,
            express_eligible=eligible,
            decision="oui" if eligible else "non",
            probability=round(probability, 4),
            model_version=self.model_version,
            predicted_at=datetime.now(timezone.utc),
            latency_ms=round((time.perf_counter() - start) * 1000, 3),
        )
