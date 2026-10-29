"""Contrat de données des commandes ERP : validateur, conversion des documents, période."""
from datetime import date, datetime

import pytest

from express_delivery.domain.order_record import OrderPeriod
from express_delivery.domain.order_validation import InvalidOrderError, OrderRecordValidator
from express_delivery.infrastructure.mongo.order_document_mapper import OrderDocumentMapper
from tests.erp_orders import erp_document

MONDAY = date(2024, 6, 17)
SATURDAY = date(2024, 6, 15)


@pytest.fixture
def mapper():
    return OrderDocumentMapper()


def test_valid_document_becomes_a_record(mapper):
    record = mapper.to_record(erp_document(1, SATURDAY))
    assert record.order_id == "ERP-00000001"
    assert record.order_date == SATURDAY and not isinstance(record.order_date, datetime)
    assert record.features["weekend"] == 1 and record.features["carrier_capacity"] == 27.3


@pytest.mark.parametrize("override", [
    {"hour": 24},
    {"hour": 9.5},
    {"stock_available": 2},
    {"stock_available": True},                 # un booléen n'est pas un entier 0/1
    {"distance_km": -0.1},
    {"order_value_eur": "89.90"},
    {"weight_kg": float("nan")},
    {"carrier_capacity": float("inf")},
    {"weather": "normal"},                     # modalité du jeu synthétique, pas de l'ERP
    {"delivery_zone": "rurale"},
    {"customer_type": "premium"},
    {"preparation_time_min": None},            # NULL d'avant 2017 dans PostgreSQL
    {"day_of_week": 0},                        # samedi déclaré lundi
    {"weekend": 0},                            # samedi non marqué week-end
])
def test_contract_violations_are_rejected(mapper, override):
    with pytest.raises(InvalidOrderError, match="ERP-00000001"):
        mapper.to_record(erp_document(1, SATURDAY, **override))


@pytest.mark.parametrize("document", [
    {**erp_document(1, MONDAY), "order_id": ""},
    {**erp_document(1, MONDAY), "order_id": 42},
    {**erp_document(1, MONDAY), "order_date": "2024-06-17"},
    {"order_id": "ERP-00000001"},
])
def test_unusable_documents_are_rejected(mapper, document):
    with pytest.raises(InvalidOrderError):
        mapper.to_record(document)


def test_missing_field_is_reported_by_name(mapper):
    document = erp_document(1, MONDAY)
    del document["weather"]
    with pytest.raises(InvalidOrderError, match="weather"):
        mapper.to_record(document)


def test_validator_lists_every_error(mapper):
    with pytest.raises(InvalidOrderError) as error:
        mapper.to_record(erp_document(1, MONDAY, hour=30, weather="orage"))
    assert "hour=30" in str(error.value) and "weather='orage'" in str(error.value)


def test_validator_accepts_other_categories():
    custom = {"weather": frozenset({"normal"}), "delivery_zone": frozenset({"centre"}),
              "customer_type": frozenset({"premium"})}
    mapper = OrderDocumentMapper(OrderRecordValidator(custom))
    document = erp_document(1, MONDAY, weather="normal", customer_type="premium")
    assert mapper.to_record(document).features["weather"] == "normal"


def test_validator_requires_every_categorical_feature():
    with pytest.raises(ValueError):
        OrderRecordValidator({"weather": frozenset({"clear"})})


def test_period_rejects_empty_interval():
    with pytest.raises(ValueError):
        OrderPeriod(MONDAY, MONDAY)


def test_period_contains_is_half_open():
    period = OrderPeriod(SATURDAY, MONDAY)
    assert period.contains(SATURDAY) and not period.contains(MONDAY)
    assert OrderPeriod().contains(date(2015, 1, 1))
