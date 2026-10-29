"""Port OrderRepository : même suite pour la mémoire et MongoDB (substitution de Liskov)."""
import logging
from datetime import date

import mongomock
import pytest
from pymongo.errors import ServerSelectionTimeoutError

from express_delivery.abstractions.order_repository import OrderSourceError
from express_delivery.domain.order_record import OrderPeriod
from express_delivery.domain.order_validation import InvalidOrderError
from express_delivery.infrastructure.memory.order_repository import InMemoryOrderRepository
from express_delivery.infrastructure.mongo.order_repository import MongoOrderRepository, period_filter
from tests.erp_orders import INSERTION_ORDER, ORDER_DATES, erp_document, erp_record

IDS = ["ERP-00000001", "ERP-00000002", "ERP-00000003"]


@pytest.fixture
def collection():
    """Collection MongoDB simulée, remplie comme le ferait l'ETL."""
    orders = mongomock.MongoClient()["livraison_express"]["orders"]
    orders.create_index("order_id", unique=True)
    orders.insert_many([erp_document(seq, ORDER_DATES[seq]) for seq in INSERTION_ORDER])
    return orders


@pytest.fixture(params=["memory", "mongo"])
def repository(request, collection):
    if request.param == "memory":
        return InMemoryOrderRepository(erp_record(seq, ORDER_DATES[seq]) for seq in INSERTION_ORDER)
    return MongoOrderRepository(collection, batch_size=2)  # lots de 2 : la pagination est exercée


# --- Contrat commun -----------------------------------------------------------------------------

def test_get_returns_the_record(repository):
    record = repository.get("ERP-00000002")
    assert record == erp_record(2, ORDER_DATES[2])
    assert isinstance(record.order_date, date) and record.order_date == date(2024, 6, 15)


def test_get_unknown_returns_none(repository):
    assert repository.get("ERP-99999999") is None


def test_get_all_returns_every_record_sorted_by_id(repository):
    assert [record.order_id for record in repository.get_all()] == IDS


@pytest.mark.parametrize(("period", "expected"), [
    (OrderPeriod(start=date(2024, 6, 15)), IDS[1:]),                      # début inclus
    (OrderPeriod(end=date(2024, 6, 15)), IDS[:1]),                        # fin exclue
    (OrderPeriod(date(2024, 1, 1), date(2025, 1, 1)), IDS[1:2]),
    (OrderPeriod(date(2026, 1, 1)), []),
])
def test_get_all_filters_on_half_open_period(repository, period, expected):
    assert [record.order_id for record in repository.get_all(period)] == expected


def test_records_expose_model_features(repository):
    row = repository.get("ERP-00000001").as_row()
    assert row["order_id"] == "ERP-00000001" and row["weather"] == "clear"


# --- Spécifique MongoDB -------------------------------------------------------------------------

def test_invalid_documents_are_skipped_and_counted(collection, caplog):
    collection.insert_many([
        erp_document(4, date(2024, 1, 1), weather="orage"),                  # modalité inconnue
        erp_document(5, date(2024, 1, 1), preparation_time_min=None),        # valeur absente
        {"order_id": "ERP-00000006", "order_date": "2024-01-01"},            # document incomplet
    ])
    with caplog.at_level(logging.WARNING):
        records = MongoOrderRepository(collection).get_all()
    assert [record.order_id for record in records] == IDS
    assert "3 document(s) rejeté(s)" in caplog.text


def test_get_raises_on_invalid_document(collection):
    collection.insert_one(erp_document(4, date(2024, 1, 1), carrier_capacity=-1))
    with pytest.raises(InvalidOrderError, match="ERP-00000004"):
        MongoOrderRepository(collection).get("ERP-00000004")


def test_repository_never_writes(collection):
    before = list(collection.find({}, {"_id": 0}))
    repository = MongoOrderRepository(collection)
    repository.get_all()
    repository.get("ERP-00000001")
    assert list(collection.find({}, {"_id": 0})) == before


def test_mongo_id_is_not_exposed(collection):
    record = MongoOrderRepository(collection).get("ERP-00000001")
    assert "_id" not in record.as_row()


class _UnreachableCollection:
    """Collection dont le serveur ne répond pas."""

    def find_one(self, *_args, **_kwargs):
        raise ServerSelectionTimeoutError("localhost:27017: timed out")

    def find(self, *_args, **_kwargs):
        raise ServerSelectionTimeoutError("localhost:27017: timed out")


@pytest.mark.parametrize("call", [lambda repo: repo.get("ERP-1"), lambda repo: repo.get_all()])
def test_driver_errors_become_order_source_error(call):
    with pytest.raises(OrderSourceError, match="timed out"):
        call(MongoOrderRepository(_UnreachableCollection()))


def test_period_filter_translates_dates_to_midnight_datetimes():
    query = period_filter(OrderPeriod(date(2024, 1, 1), date(2024, 2, 1)))
    assert query == {"order_date": {"$gte": erp_document(1, date(2024, 1, 1))["order_date"],
                                    "$lt": erp_document(1, date(2024, 2, 1))["order_date"]}}
    assert not period_filter(OrderPeriod())


def test_batch_size_must_be_positive(collection):
    with pytest.raises(ValueError):
        MongoOrderRepository(collection, batch_size=0)
