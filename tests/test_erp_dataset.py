"""Jeu d'entraînement issu de l'ERP (ADR-0012) : de la commande lue au modèle entraîné."""
from datetime import date

import pandas as pd
import pytest

from express_delivery.domain.express_eligibility import ExpressEligibilityRule
from express_delivery.domain.features import FEATURE_COLUMNS, TARGET_COLUMN
from express_delivery.domain.order_record import OrderPeriod, OrderRecord
from express_delivery.domain.order_translation import ErpOrderTranslator
from express_delivery.infrastructure.memory.order_repository import InMemoryOrderRepository
from express_delivery.ml.dataset import clean_orders_data, validate_dataset
from express_delivery.ml.erp_dataset import ErpTrainingDataBuilder
from express_delivery.ml.feature_frame import build_feature_frame
from tests.conftest import EASY_ORDER, HARD_ORDER, build_test_trainer
from tests.erp_orders import erp_record, simulated_erp_records
from tests.fakes import RecordingExperimentTracker


@pytest.fixture
def builder() -> ErpTrainingDataBuilder:
    return ErpTrainingDataBuilder(ErpOrderTranslator(), ExpressEligibilityRule())


@pytest.fixture(scope="module")
def records() -> list[OrderRecord]:
    return simulated_erp_records(1500)


def test_frame_has_identity_features_and_target(builder, records):
    frame = builder.build(records)
    assert len(frame) == len(records)
    assert {"order_id", "order_date", *FEATURE_COLUMNS, TARGET_COLUMN} <= set(frame.columns)
    assert set(frame[TARGET_COLUMN].unique()) == {0, 1}


def test_target_follows_the_business_rule(builder, records):
    frame = builder.build(records)
    rule = ExpressEligibilityRule()
    for row in frame.head(50).to_dict("records"):
        assert row[TARGET_COLUMN] == int(rule.is_eligible(row))


def test_eligible_share_is_a_minority_but_learnable(builder, records):
    share = builder.build(records)[TARGET_COLUMN].mean()
    assert 0.05 < share < 0.40


def test_frame_passes_the_existing_quality_checks(builder, records):
    data = clean_orders_data(builder.build(records))
    validate_dataset(data)  # carrier_capacity dans [0, 1], doublons, bornes...
    assert len(data) == len(records)


def test_untranslatable_orders_are_skipped_and_counted(builder, records, caplog):
    bad = OrderRecord("ERP-BAD", date(2024, 1, 2), {**records[0].features, "weather": "fog"})
    with caplog.at_level("WARNING"):
        frame = builder.build([*records, bad])
    assert len(frame) == len(records)
    assert "1 commande(s) écartée(s)" in caplog.text


def test_no_usable_order_is_an_error(builder):
    with pytest.raises(ValueError, match="Aucune commande exploitable"):
        builder.build([])


def test_a_single_class_is_an_error(builder):
    only_rejected_by_rule = [
        OrderRecord(f"ERP-{i}", date(2024, 1, 2), {**erp_record(i, date(2024, 1, 2)).features, "stock_available": 0})
        for i in range(1, 20)
    ]
    with pytest.raises(ValueError, match="une seule classe"):
        builder.build(only_rejected_by_rule)


def test_period_selects_which_orders_train_the_model(builder, records):
    repository = InMemoryOrderRepository(records)
    period = OrderPeriod(date(2023, 1, 1), date(2023, 7, 1))
    selected = repository.get_all(period)
    assert 0 < len(selected) < len(records)
    assert len(builder.build(selected)) == len(selected)


def test_a_model_trained_on_erp_data_serves_the_existing_api_contract(builder, records):
    data = clean_orders_data(builder.build(records))
    result = build_test_trainer(RecordingExperimentTracker()).train(data)
    assert result.metrics["roc_auc"] > 0.85  # la règle est apprenable à partir des variables
    probabilities = result.pipeline.predict_proba(
        build_feature_frame([{"order_id": "CMD-1", **EASY_ORDER}, {"order_id": "CMD-2", **HARD_ORDER}])
    )[:, 1]
    assert probabilities[0] > 0.5 > probabilities[1]
    assert isinstance(data, pd.DataFrame)
