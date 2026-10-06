"""Cas d'usage « collecter une commande » (POST /v1/orders)."""
from __future__ import annotations

import uuid
from typing import Any, Callable, Mapping

from express_delivery.abstractions.order_store import OrderStore
from express_delivery.domain.models import Order


def generate_order_id() -> str:
    return f"CMD-{uuid.uuid4().hex[:12].upper()}"


class OrderService:
    def __init__(
        self,
        store: OrderStore,
        id_generator: Callable[[], str] = generate_order_id,
    ) -> None:
        self._store = store
        self._id_generator = id_generator

    def resolve_id(self, order_id: str | None) -> str:
        return order_id or self._id_generator()

    def register(self, order_id: str | None, features: Mapping[str, Any]) -> Order:
        order = Order(order_id=self.resolve_id(order_id), features=dict(features))
        self._store.save(order)
        # Séance 5 : publier ici la commande dans une file pour prédiction asynchrone.
        return order

    def get(self, order_id: str) -> Order | None:
        return self._store.get(order_id)
