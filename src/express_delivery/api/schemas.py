"""Schémas HTTP : traduction exacte des components/schemas de openapi.yml."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Weather = Literal["normal", "pluie", "neige", "orage"]
DeliveryZone = Literal["centre", "proche_banlieue", "banlieue", "rurale"]
CustomerType = Literal["standard", "premium"]


class OrderFeatures(BaseModel):
    """Caractéristiques d'une commande. Toute variable absente ou en trop -> 422."""

    model_config = ConfigDict(extra="forbid")

    order_id: str | None = Field(
        default=None,
        description="Identifiant métier de la commande. Généré par le serveur si absent.",
        examples=["CMD-000001"],
    )
    hour: int = Field(ge=0, le=23, examples=[14])
    day_of_week: int = Field(ge=0, le=6, description="0 = lundi ... 6 = dimanche", examples=[2])
    weekend: Literal[0, 1] = Field(examples=[0])
    distance_km: float = Field(ge=0, examples=[3.5])
    order_value_eur: float = Field(ge=0, examples=[89.9])
    weight_kg: float = Field(ge=0, examples=[2.4])
    stock_available: Literal[0, 1] = Field(examples=[1])
    preparation_time_min: float = Field(ge=0, examples=[18])
    carrier_capacity: float = Field(ge=0, le=1, examples=[0.85])
    weather: Weather
    delivery_zone: DeliveryZone
    customer_type: CustomerType

    def model_features(self) -> dict:
        """Les 12 variables du modèle, sans l'identifiant."""
        return self.model_dump(exclude={"order_id"})


class OrderAccepted(BaseModel):
    order_id: str
    status: Literal["accepted"] = "accepted"


class Prediction(BaseModel):
    order_id: str
    express_eligible: bool
    decision: Literal["oui", "non"]
    probability: float = Field(ge=0, le=1)
    model_version: str
    predicted_at: datetime
    latency_ms: float | None = None


class HealthStatus(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str


class ReadinessStatus(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str]
    version: str | None = None


class Error(BaseModel):
    error: str = Field(description="Code d'erreur stable, branchable côté client")
    message: str = Field(description="Message destiné à l'humain, non contractuel")
    details: list[str] | None = None
