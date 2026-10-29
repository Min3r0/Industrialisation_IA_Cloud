"""Implémentation MongoDB de OrderRepository : base analytique `livraison_express.orders` (ADR-0011).

Lecture seule : aucune méthode de ce module n'écrit dans la collection alimentée par
l'ETL. Les requêtes sont filtrées par `order_date`, triées sur `order_id` (index
unique créé par l'ETL), projetées sur les seuls champs utiles et lues par lots.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any

from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from express_delivery.abstractions.order_repository import OrderRepository, OrderSourceError
from express_delivery.domain.order_record import OrderPeriod, OrderRecord
from express_delivery.domain.order_validation import InvalidOrderError
from express_delivery.infrastructure.mongo.order_document_mapper import ORDER_PROJECTION, OrderDocumentMapper

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 1000


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time.min)


def period_filter(period: OrderPeriod) -> dict[str, Any]:
    """Filtre MongoDB équivalent à OrderPeriod.contains (order_date est un datetime)."""
    bounds: dict[str, datetime] = {}
    if period.start is not None:
        bounds["$gte"] = _midnight(period.start)
    if period.end is not None:
        bounds["$lt"] = _midnight(period.end)
    return {"order_date": bounds} if bounds else {}


class MongoOrderRepository(OrderRepository):
    """Lit les commandes d'une collection MongoDB ouverte (voir connection.py)."""

    def __init__(
        self,
        collection: Collection,
        mapper: OrderDocumentMapper | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size doit être >= 1.")
        self._collection = collection
        self._mapper = mapper or OrderDocumentMapper()
        self._batch_size = batch_size

    def get(self, order_id: str) -> OrderRecord | None:
        try:
            document = self._collection.find_one({"order_id": order_id}, ORDER_PROJECTION)
        except PyMongoError as error:
            raise OrderSourceError(f"Lecture de la commande {order_id!r} impossible : {error}") from error
        return None if document is None else self._mapper.to_record(document)

    def get_all(self, period: OrderPeriod | None = None) -> list[OrderRecord]:
        query = period_filter(period or OrderPeriod())
        records: list[OrderRecord] = []
        rejected = 0
        try:
            cursor = (
                self._collection.find(query, ORDER_PROJECTION)
                .sort("order_id", ASCENDING)
                .batch_size(self._batch_size)
            )
            for document in cursor:
                try:
                    records.append(self._mapper.to_record(document))
                except InvalidOrderError as error:
                    rejected += 1
                    logger.debug("Document rejeté : %s", error)
        except PyMongoError as error:
            raise OrderSourceError(f"Lecture des commandes impossible : {error}") from error

        if rejected:
            logger.warning("%d document(s) rejeté(s) par la validation sur %d lus", rejected, rejected + len(records))
        logger.info("%d commande(s) lue(s) dans MongoDB (filtre %s)", len(records), query or "aucun")
        return records
