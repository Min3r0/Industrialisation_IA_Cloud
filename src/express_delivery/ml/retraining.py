"""Orchestration du réentraînement périodique (ADR-0013, point j de la checklist).

Enchaîne trois étapes, dans l'ordre :
1. lecture des commandes récentes dans la source (port `OrderRepository`, avec nouvelles tentatives) ;
2. contrôle de fraîcheur : assez de commandes dans la fenêtre, sinon rien n'est entraîné ;
3. publication d'une nouvelle version, si elle n'existe pas déjà (une exécution répétée le même jour ne refait rien).

Le pipeline ne lit pas MongoDB, n'entraîne pas et n'écrit pas de fichier : il reçoit ces
capacités sous forme de fonctions (inversion des dépendances) et se teste sans base ni modèle.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Sequence

from express_delivery.abstractions.order_repository import OrderRepository, OrderSourceError
from express_delivery.domain.order_record import OrderPeriod, OrderRecord

logger = logging.getLogger(__name__)

STATUS_PUBLISHED = "published"
STATUS_SKIPPED = "skipped"

Publisher = Callable[[Sequence[OrderRecord], str], None]


@dataclass(frozen=True)
class RetrainingPolicy:
    """Règles de déclenchement (ADR-0013). Les valeurs par défaut sont des hypothèses d'exploitation."""

    freshness_window_days: int = 30
    min_recent_orders: int = 500
    max_attempts: int = 3
    retry_delay_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.freshness_window_days < 1 or self.min_recent_orders < 1 or self.max_attempts < 1:
            raise ValueError("Fenêtre, minimum de commandes et tentatives doivent être strictement positifs.")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds ne peut pas être négatif.")


@dataclass(frozen=True)
class Clock:
    """Horloge injectée : date du jour et pause entre tentatives (remplaçable en test)."""

    today: Callable[[], date] = date.today
    sleep: Callable[[float], None] = time.sleep


@dataclass(frozen=True)
class RetrainingOutcome:
    """Résultat d'une exécution : publié, ou sauté avec la raison."""

    status: str
    version: str
    detail: str


class RetrainingPipeline:
    """Seule responsabilité : décider si l'on réentraîne, et dans quel ordre."""

    def __init__(
        self,
        repository: OrderRepository,
        publish: Publisher,
        version_exists: Callable[[str], bool],
        policy: RetrainingPolicy | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._publish = publish
        self._version_exists = version_exists
        self._policy = policy or RetrainingPolicy()
        self._clock = clock or Clock()

    def run(self, version: str) -> RetrainingOutcome:
        """Lève OrderSourceError si la source reste injoignable après toutes les tentatives."""
        if self._version_exists(version):
            return RetrainingOutcome(STATUS_SKIPPED, version, "version déjà publiée, rien à faire")

        records = self._read_recent_orders()
        minimum = self._policy.min_recent_orders
        if len(records) < minimum:
            return RetrainingOutcome(
                STATUS_SKIPPED, version,
                f"{len(records)} commande(s) dans la fenêtre, minimum {minimum} : entraînement non lancé",
            )

        self._publish(records, version)
        return RetrainingOutcome(STATUS_PUBLISHED, version, f"{len(records)} commandes récentes")

    def _read_recent_orders(self) -> list[OrderRecord]:
        today = self._clock.today()
        window = self._policy.freshness_window_days
        period = OrderPeriod(today - timedelta(days=window), today + timedelta(days=1))
        for attempt in range(1, self._policy.max_attempts):
            try:
                return self._repository.get_all(period)
            except OrderSourceError as error:
                delay = self._policy.retry_delay_seconds * attempt
                logger.warning(
                    "Lecture des commandes échouée (tentative %d/%d) : %s. Nouvel essai dans %.0f s.",
                    attempt, self._policy.max_attempts, error, delay,
                )
                self._clock.sleep(delay)
        return self._repository.get_all(period)  # dernière tentative : l'erreur remonte à l'appelant
