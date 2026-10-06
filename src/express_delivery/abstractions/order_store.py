"""Port de persistance des commandes (ADR-0001).

Les couches service et API dépendent de cette abstraction, jamais d'une base
concrète (principe d'inversion des dépendances).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from express_delivery.domain.models import Order


class OrderStore(ABC):
    @abstractmethod
    def save(self, order: Order) -> None:
        """Persiste une commande. Ré-enregistrer un order_id existant le remplace."""

    @abstractmethod
    def get(self, order_id: str) -> Order | None:
        """Retourne la commande ou None si elle est inconnue."""

    @abstractmethod
    def is_reachable(self) -> bool:
        """Indique si le stockage répond (utilisé par /health/ready)."""
