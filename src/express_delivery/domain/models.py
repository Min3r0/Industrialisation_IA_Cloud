"""Objets métier, indépendants de FastAPI, de SQLite et de scikit-learn."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class OrderStatus(str, Enum):
    PENDING = "pending"  # collectée, en attente de prédiction (asynchrone, séance 5)


@dataclass(frozen=True)
class Order:
    order_id: str
    features: Mapping[str, Any]
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PredictionResult:
    order_id: str
    express_eligible: bool
    decision: str
    probability: float
    model_version: str
    predicted_at: datetime
    latency_ms: float


@dataclass(frozen=True)
class ModelMetadata:
    """Contenu du manifeste d'une version de modèle (voir ADR-0002)."""

    model_version: str
    model_type: str
    target: str
    features: tuple[str, ...]
    metrics: Mapping[str, float]
    trained_at: str
    sklearn_version: str
