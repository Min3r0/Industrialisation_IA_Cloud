"""Commandes historiques lues dans la source de données de l'entreprise (ADR-0011).

À ne pas confondre avec `Order` : une `Order` est collectée par l'API et attend sa
prédiction ; un `OrderRecord` est une commande passée par l'ERP, lue (jamais écrite)
pour entraîner ou évaluer le modèle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping


@dataclass(frozen=True)
class OrderRecord:
    """Commande passée par l'ERP : identifiant, jour de commande et variables du modèle."""

    order_id: str
    order_date: date
    features: Mapping[str, Any] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        """Ligne plate (identifiant, date, variables), prête pour un DataFrame."""
        return {"order_id": self.order_id, "order_date": self.order_date, **self.features}


@dataclass(frozen=True)
class OrderPeriod:
    """Intervalle de dates semi-ouvert [start, end[ ; une borne absente n'est pas filtrée."""

    start: date | None = None
    end: date | None = None

    def __post_init__(self) -> None:
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("La date de début doit précéder strictement la date de fin.")

    def contains(self, day: date) -> bool:
        """Indique si le jour appartient à la période."""
        after_start = self.start is None or day >= self.start
        before_end = self.end is None or day < self.end
        return after_start and before_end
