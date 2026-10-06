import pytest

from express_delivery.domain.models import Order
from express_delivery.infrastructure.memory.order_store import InMemoryOrderStore
from express_delivery.infrastructure.sqlite.order_store import SqliteOrderStore
from tests.conftest import EASY_ORDER


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    # Même suite de tests pour toutes les implémentations (substitution de Liskov)
    if request.param == "memory":
        return InMemoryOrderStore()
    return SqliteOrderStore(tmp_path / "sub" / "orders.db")


def test_save_then_get_returns_same_order(store):
    store.save(Order("CMD-1", EASY_ORDER))
    loaded = store.get("CMD-1")
    assert loaded.order_id == "CMD-1"
    assert dict(loaded.features) == EASY_ORDER


def test_get_unknown_returns_none(store):
    assert store.get("absent") is None


def test_saving_same_id_replaces_order(store):
    store.save(Order("CMD-1", EASY_ORDER))
    store.save(Order("CMD-1", {**EASY_ORDER, "hour": 9}))
    assert store.get("CMD-1").features["hour"] == 9


def test_store_is_reachable(store):
    assert store.is_reachable()


def test_sqlite_persists_across_instances(tmp_path):
    SqliteOrderStore(tmp_path / "orders.db").save(Order("CMD-1", EASY_ORDER))
    assert SqliteOrderStore(tmp_path / "orders.db").get("CMD-1") is not None
