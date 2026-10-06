"""Implémentation en mémoire de OrderStore, pour les tests unitaires."""
from __future__ import annotations

from express_delivery.abstractions.order_store import OrderStore
from express_delivery.domain.models import Order


class InMemoryOrderStore(OrderStore):
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def is_reachable(self) -> bool:
        return True
