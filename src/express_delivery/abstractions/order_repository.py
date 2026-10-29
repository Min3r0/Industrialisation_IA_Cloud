"""Port de lecture des commandes de l'entreprise (ADR-0011).

Distinct de `OrderStore` (ségrégation des interfaces) : l'entraînement lit des
commandes, il n'en écrit jamais. Aucune méthode `save` n'est donc exposée : la source
(base analytique alimentée par l'ETL) est en lecture seule pour l'application.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from express_delivery.domain.order_record import OrderPeriod, OrderRecord


class OrderSourceError(Exception):
    """La source de commandes est injoignable ou a refusé la requête."""


class OrderRepository(ABC):
    """Lecture seule des commandes passées, quelle que soit la base qui les contient."""

    @abstractmethod
    def get(self, order_id: str) -> OrderRecord | None:
        """Retourne la commande, None si elle est inconnue.

        Lève InvalidOrderError si la commande existe mais viole le contrat de données,
        OrderSourceError si la source ne répond pas.
        """

    @abstractmethod
    def get_all(self, period: OrderPeriod | None = None) -> list[OrderRecord]:
        """Commandes valides de la période (toutes si None), triées par order_id.

        Une commande invalide est écartée et comptée dans les logs : elle ne fait pas
        échouer tout le chargement. Lève OrderSourceError si la source ne répond pas.
        """
