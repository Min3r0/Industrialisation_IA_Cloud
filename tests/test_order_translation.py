"""Traduction ERP → domaine (ADR-0012) : le contrat de l'API ne doit pas changer."""
from datetime import date
from typing import get_args

import pytest

from express_delivery.api.schemas import CustomerType, DeliveryZone, Weather
from express_delivery.domain.order_record import OrderRecord
from express_delivery.domain.order_translation import CARRIER_CAPACITY_MAX, MODALITY_MAP, ErpOrderTranslator
from express_delivery.domain.order_validation import SOURCE_CATEGORIES, InvalidOrderError
from tests.erp_orders import erp_record


@pytest.fixture
def translator() -> ErpOrderTranslator:
    return ErpOrderTranslator()


def _with(record: OrderRecord, **changes) -> OrderRecord:
    return OrderRecord(record.order_id, record.order_date, {**record.features, **changes})


def test_every_erp_modality_has_a_translation():
    assert {name: set(table) for name, table in MODALITY_MAP.items()} == {
        name: set(values) for name, values in SOURCE_CATEGORIES.items()
    }


def test_translations_stay_inside_the_api_contract():
    allowed = {"weather": set(get_args(Weather)), "delivery_zone": set(get_args(DeliveryZone)),
               "customer_type": set(get_args(CustomerType))}
    for name, table in MODALITY_MAP.items():
        assert set(table.values()) <= allowed[name]


def test_modalities_and_capacity_are_translated(translator):
    record = erp_record(1, date(2024, 3, 4))  # clear / centre / business / capacité 27,3
    translated = translator.translate(_with(record, weather="snow", delivery_zone="suburb", customer_type="individual"))
    assert translated.features["weather"] == "neige"
    assert translated.features["delivery_zone"] == "banlieue"
    assert translated.features["customer_type"] == "standard"
    assert translated.features["carrier_capacity"] == pytest.approx(27.3 / CARRIER_CAPACITY_MAX, abs=1e-4)


def test_capacity_always_ends_up_between_0_and_1(translator):
    record = erp_record(1, date(2024, 3, 4))
    for capacity in (5, 27.3, 50):
        translated = translator.translate(_with(record, carrier_capacity=capacity))
        assert 0 <= translated.features["carrier_capacity"] <= 1


def test_other_features_and_identity_are_untouched(translator):
    record = erp_record(7, date(2024, 3, 4))
    translated = translator.translate(record)
    assert (translated.order_id, translated.order_date) == (record.order_id, record.order_date)
    for name in ("hour", "distance_km", "weight_kg", "stock_available", "preparation_time_min"):
        assert translated.features[name] == record.features[name]


def test_translation_does_not_modify_the_source_record(translator):
    record = erp_record(1, date(2024, 3, 4))
    translator.translate(record)
    assert record.features["weather"] == "clear"
    assert record.features["carrier_capacity"] == 27.3


def test_unknown_modality_is_refused(translator):
    with pytest.raises(InvalidOrderError, match="sans équivalent"):
        translator.translate(_with(erp_record(1, date(2024, 3, 4)), weather="fog"))


def test_capacity_above_the_known_maximum_is_refused(translator):
    with pytest.raises(InvalidOrderError, match="dépasse"):
        translator.translate(_with(erp_record(1, date(2024, 3, 4)), carrier_capacity=80))
