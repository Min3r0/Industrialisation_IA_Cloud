"""Conversion document MongoDB → OrderRecord validé (ADR-0011).

Seule responsabilité : connaître la forme d'un document de `livraison_express.orders`
(champs à lire, type de `order_date`) et produire un objet du domaine contrôlé.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from express_delivery.domain.features import FEATURE_COLUMNS
from express_delivery.domain.order_record import OrderRecord
from express_delivery.domain.order_validation import InvalidOrderError, OrderRecordValidator

# Projection : seuls les champs utiles transitent sur le réseau, jamais `_id`.
ORDER_PROJECTION: Mapping[str, int] = {
    "_id": 0,
    "order_id": 1,
    "order_date": 1,
    **{name: 1 for name in FEATURE_COLUMNS},
}


def _to_date(value: Any) -> date:
    """L'ETL stocke order_date en datetime (minuit) : seul le jour est conservé."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise InvalidOrderError(f"order_date={value!r} n'est pas une date")


class OrderDocumentMapper:
    """Traduit un document de la collection en OrderRecord validé."""

    def __init__(self, validator: OrderRecordValidator | None = None) -> None:
        self._validator = validator or OrderRecordValidator()

    def to_record(self, document: Mapping[str, Any]) -> OrderRecord:
        """Lève InvalidOrderError si le document est inexploitable."""
        order_id = document.get("order_id")
        if not isinstance(order_id, str) or not order_id.strip():
            raise InvalidOrderError(f"order_id={order_id!r} absent ou invalide")
        try:
            order_date = _to_date(document.get("order_date"))
        except InvalidOrderError as error:
            raise InvalidOrderError(f"Commande {order_id!r} invalide : {error}") from error

        record = OrderRecord(
            order_id=order_id,
            order_date=order_date,
            features={name: document.get(name) for name in FEATURE_COLUMNS},
        )
        self._validator.validate(record)
        return record
