"""Contrat de données des commandes de l'ERP (ADR-0011 : « valider les données dans l'application »).

La base analytique n'impose aucun schéma : chaque commande lue est contrôlée ici avant
d'entrer dans l'application (types, bornes, modalités autorisées, cohérence des dates).
Les modalités sont celles de l'ERP ; leur correspondance avec celles du modèle actuel
relève de l'étape d'intégration des données, pas de la lecture.
"""
from __future__ import annotations

import math
from types import MappingProxyType
from typing import Any, Mapping

from express_delivery.domain.features import CATEGORICAL_FEATURES, FEATURE_COLUMNS
from express_delivery.domain.order_record import OrderRecord

# Modalités observées dans l'ERP (simulateur tp4-bdd.zip, generator.py)
SOURCE_CATEGORIES: Mapping[str, frozenset[str]] = MappingProxyType({
    "weather": frozenset({"clear", "rain", "wind", "snow"}),
    "delivery_zone": frozenset({"centre", "suburb", "rural"}),
    "customer_type": frozenset({"individual", "business"}),
})

_INTEGER_BOUNDS: Mapping[str, tuple[int, int]] = {
    "hour": (0, 23),
    "day_of_week": (0, 6),
    "weekend": (0, 1),
    "stock_available": (0, 1),
}

_NON_NEGATIVE_NUMBERS: tuple[str, ...] = (
    "distance_km",
    "order_value_eur",
    "weight_kg",
    "preparation_time_min",
    "carrier_capacity",
)

_WEEKEND_START = 5  # samedi (date.weekday())


class InvalidOrderError(ValueError):
    """Une commande lue dans la source ne respecte pas le contrat de données."""


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (_is_integer(value) or isinstance(value, float)) and math.isfinite(value)


class OrderRecordValidator:
    """Seule responsabilité : dire si une commande est exploitable, et pourquoi sinon."""

    def __init__(self, categories: Mapping[str, frozenset[str]] | None = None) -> None:
        """`categories` : modalités autorisées par variable catégorielle (ERP par défaut)."""
        categories = SOURCE_CATEGORIES if categories is None else categories
        unknown = set(categories) ^ set(CATEGORICAL_FEATURES)
        if unknown:
            raise ValueError(f"Variables catégorielles inattendues : {sorted(unknown)}")
        self._categories = categories

    def validate(self, record: OrderRecord) -> None:
        """Lève InvalidOrderError au premier écart, avec l'identifiant de la commande."""
        errors = self.errors(record)
        if errors:
            raise InvalidOrderError(f"Commande {record.order_id!r} invalide : {'; '.join(errors)}")

    def errors(self, record: OrderRecord) -> list[str]:
        """Liste de tous les écarts au contrat (vide si la commande est valide)."""
        features = record.features
        missing = [name for name in FEATURE_COLUMNS if features.get(name) is None]
        if missing:
            return [f"valeurs absentes {missing}"]
        return [
            *self._integer_errors(features),
            *self._number_errors(features),
            *self._category_errors(features),
            *self._calendar_errors(record),
        ]

    @staticmethod
    def _integer_errors(features: Mapping[str, Any]) -> list[str]:
        return [
            f"{name}={features[name]!r} hors de [{low}, {high}]"
            for name, (low, high) in _INTEGER_BOUNDS.items()
            if not (_is_integer(features[name]) and low <= features[name] <= high)
        ]

    @staticmethod
    def _number_errors(features: Mapping[str, Any]) -> list[str]:
        return [
            f"{name}={features[name]!r} doit être un nombre positif ou nul"
            for name in _NON_NEGATIVE_NUMBERS
            if not (_is_number(features[name]) and features[name] >= 0)
        ]

    def _category_errors(self, features: Mapping[str, Any]) -> list[str]:
        return [
            f"{name}={features[name]!r} hors de {sorted(allowed)}"
            for name, allowed in self._categories.items()
            if features[name] not in allowed
        ]

    @staticmethod
    def _calendar_errors(record: OrderRecord) -> list[str]:
        """day_of_week et weekend doivent découler de order_date (données dérivées)."""
        weekday = record.order_date.weekday()
        expected = {"day_of_week": weekday, "weekend": int(weekday >= _WEEKEND_START)}
        return [
            f"{name}={record.features[name]!r} incohérent avec order_date={record.order_date} (attendu {value})"
            for name, value in expected.items()
            if record.features[name] != value
        ]
