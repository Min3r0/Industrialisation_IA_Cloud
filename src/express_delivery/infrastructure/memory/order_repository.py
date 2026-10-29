"""Implémentation en mémoire de OrderRepository, pour les tests unitaires."""
from __future__ import annotations

from typing import Iterable

from express_delivery.abstractions.order_repository import OrderRepository
from express_delivery.domain.order_record import OrderPeriod, OrderRecord


class InMemoryOrderRepository(OrderRepository):
    """Commandes fournies au constructeur : aucune base, aucune validation (déjà du domaine)."""

    def __init__(self, records: Iterable[OrderRecord] = ()) -> None:
        self._records = {record.order_id: record for record in records}

    def get(self, order_id: str) -> OrderRecord | None:
        return self._records.get(order_id)

    def get_all(self, period: OrderPeriod | None = None) -> list[OrderRecord]:
        period = period or OrderPeriod()
        return sorted(
            (record for record in self._records.values() if period.contains(record.order_date)),
            key=lambda record: record.order_id,
        )
