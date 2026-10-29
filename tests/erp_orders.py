"""Commandes au format de l'ERP, pour les tests de lecture (ADR-0011).

Reproduit la forme des documents écrits par le simulateur (`tp4-bdd.zip`,
`generator.py` + `storage.MongoWriter`) : order_date en datetime à minuit,
modalités ERP, carrier_capacity entre 5 et 50.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from express_delivery.domain.features import FEATURE_COLUMNS
from express_delivery.domain.order_record import OrderRecord


def erp_document(sequence: int, order_date: date, **overrides: Any) -> dict[str, Any]:
    weekday = order_date.weekday()
    document = {
        "order_id": f"ERP-{sequence:08d}",
        "order_date": datetime.combine(order_date, time.min),
        "hour": 8 + sequence % 12,
        "day_of_week": weekday,
        "weekend": int(weekday >= 5),
        "distance_km": 12.5,
        "order_value_eur": 89.9,
        "weight_kg": 2.4,
        "stock_available": sequence % 2,
        "preparation_time_min": 18.0,
        "carrier_capacity": 27.3,
        "weather": "clear",
        "delivery_zone": "centre",
        "customer_type": "business",
    }
    document.update(overrides)
    return document


def erp_record(sequence: int, order_date: date) -> OrderRecord:
    document = erp_document(sequence, order_date)
    return OrderRecord(
        order_id=document["order_id"],
        order_date=order_date,
        features={name: document[name] for name in FEATURE_COLUMNS},
    )


# Trois commandes valides, volontairement insérées dans le désordre
ORDER_DATES = {1: date(2023, 1, 2), 2: date(2024, 6, 15), 3: date(2025, 12, 31)}
INSERTION_ORDER = (3, 1, 2)
