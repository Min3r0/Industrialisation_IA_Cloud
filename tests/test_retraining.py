"""Orchestrateur de réentraînement (ADR-0013) : déclenchement, fraîcheur, reprises, idempotence."""
from datetime import date, timedelta

import pytest

from express_delivery.abstractions.order_repository import OrderRepository, OrderSourceError
from express_delivery.domain.features import FEATURE_COLUMNS
from express_delivery.domain.order_record import OrderPeriod, OrderRecord
from express_delivery.infrastructure.memory.order_repository import InMemoryOrderRepository
from express_delivery.ml.retraining import (
    STATUS_PUBLISHED,
    STATUS_SKIPPED,
    Clock,
    RetrainingPipeline,
    RetrainingPolicy,
)
from tests.erp_orders import simulated_erp_document

TODAY = date(2026, 11, 20)


def recent_records(count: int, days_ago: int = 0) -> list[OrderRecord]:
    """`count` commandes valides, datées `days_ago` jours avant aujourd'hui (fenêtre de 20 jours max)."""
    records = []
    for sequence in range(1, count + 1):
        day = TODAY - timedelta(days=days_ago + sequence % 20)
        document = simulated_erp_document(sequence, day)
        records.append(OrderRecord(document["order_id"], day, {name: document[name] for name in FEATURE_COLUMNS}))
    return records


class FlakyRepository(OrderRepository):
    """Source qui échoue les `failures` premières lectures, puis répond normalement."""

    def __init__(self, inner: OrderRepository, failures: int) -> None:
        self._inner = inner
        self._failures = failures
        self.calls = 0

    def get(self, order_id: str):
        return self._inner.get(order_id)

    def get_all(self, period: OrderPeriod | None = None):
        self.calls += 1
        if self.calls <= self._failures:
            raise OrderSourceError("MongoDB injoignable")
        return self._inner.get_all(period)


class Recorder:
    """Enregistre les publications et les pauses, sans rien écrire ni attendre."""

    def __init__(self) -> None:
        self.published: list[tuple[int, str]] = []
        self.sleeps: list[float] = []

    def publish(self, records, version: str) -> None:
        self.published.append((len(records), version))


def build(repository, recorder, *, exists=lambda version: False, **policy_overrides) -> RetrainingPipeline:
    policy = RetrainingPolicy(**{"min_recent_orders": 500, "retry_delay_seconds": 5, **policy_overrides})
    return RetrainingPipeline(
        repository=repository,
        publish=recorder.publish,
        version_exists=exists,
        policy=policy,
        clock=Clock(today=lambda: TODAY, sleep=recorder.sleeps.append),
    )


def test_publishes_when_enough_recent_orders():
    recorder = Recorder()
    outcome = build(InMemoryOrderRepository(recent_records(600)), recorder).run("erp-20261120")
    assert outcome.status == STATUS_PUBLISHED
    assert recorder.published == [(600, "erp-20261120")]


def test_skips_when_not_enough_recent_orders():
    recorder = Recorder()
    outcome = build(InMemoryOrderRepository(recent_records(100)), recorder).run("erp-20261120")
    assert outcome.status == STATUS_SKIPPED
    assert "minimum 500" in outcome.detail
    assert not recorder.published


def test_orders_older_than_the_window_do_not_count():
    recorder = Recorder()
    old = recent_records(600, days_ago=60)  # 60 jours avant : hors fenêtre de 30 jours
    outcome = build(InMemoryOrderRepository(old), recorder).run("erp-20261120")
    assert outcome.status == STATUS_SKIPPED
    assert not recorder.published


def test_a_version_already_published_is_not_trained_again():
    recorder = Recorder()
    repository = FlakyRepository(InMemoryOrderRepository(recent_records(600)), failures=0)
    outcome = build(repository, recorder, exists=lambda version: True).run("erp-20261120")
    assert outcome.status == STATUS_SKIPPED
    assert not recorder.published
    assert repository.calls == 0  # la source n'est même pas interrogée


def test_transient_source_error_is_retried_with_growing_delay():
    recorder = Recorder()
    repository = FlakyRepository(InMemoryOrderRepository(recent_records(600)), failures=2)
    outcome = build(repository, recorder, max_attempts=3).run("erp-20261120")
    assert outcome.status == STATUS_PUBLISHED
    assert repository.calls == 3
    assert recorder.sleeps == [5, 10]


def test_gives_up_after_the_last_attempt_and_publishes_nothing():
    recorder = Recorder()
    repository = FlakyRepository(InMemoryOrderRepository(recent_records(600)), failures=10)
    with pytest.raises(OrderSourceError):
        build(repository, recorder, max_attempts=3).run("erp-20261120")
    assert repository.calls == 3
    assert not recorder.published


@pytest.mark.parametrize("policy", [
    {"freshness_window_days": 0},
    {"min_recent_orders": 0},
    {"max_attempts": 0},
    {"retry_delay_seconds": -1},
])
def test_policy_rejects_invalid_values(policy):
    with pytest.raises(ValueError):
        RetrainingPolicy(**policy)
