"""Tests des petites classes ML : chacune testable seule (responsabilité unique)."""
import pandas as pd
import pytest

from express_delivery.domain.features import FEATURE_COLUMNS, TARGET_COLUMN
from express_delivery.ml.dataset import clean_orders_data, generate_orders_dataset
from express_delivery.ml.evaluator import ModelEvaluator
from express_delivery.ml.feature_frame import build_feature_frame
from express_delivery.ml.pipeline_factory import PipelineFactory
from express_delivery.ml.splitter import TrainTestSplitter
from express_delivery.ml.trainer import ModelTrainer
from tests.conftest import EASY_ORDER, build_test_trainer
from tests.fakes import RecordingExperimentTracker

METRICS = {"accuracy", "precision", "recall", "f1_score", "roc_auc"}


@pytest.fixture(scope="module")
def data() -> pd.DataFrame:
    return clean_orders_data(generate_orders_dataset(n_rows=1000))


def test_feature_frame_keeps_only_model_features_in_order():
    frame = build_feature_frame([{"order_id": "CMD-1", **EASY_ORDER}])
    assert list(frame.columns) == list(FEATURE_COLUMNS)
    assert len(frame) == 1


def test_pipeline_factory_builds_a_fresh_unfitted_pipeline():
    factory = PipelineFactory(random_state=7)
    assert factory.build() is not factory.build()
    assert factory.params["random_state"] == 7


def test_splitter_is_stratified_and_excludes_target(data):
    split = TrainTestSplitter(test_size=0.25).split(data)
    assert len(split.X_test) == pytest.approx(len(data) * 0.25, abs=1)
    assert TARGET_COLUMN not in split.X_train.columns
    assert split.y_train.mean() == pytest.approx(split.y_test.mean(), abs=0.02)


def test_splitter_rejects_invalid_test_size():
    with pytest.raises(ValueError):
        TrainTestSplitter(test_size=1.0)


def test_evaluator_returns_the_five_metrics(data):
    split = TrainTestSplitter().split(data)
    pipeline = PipelineFactory().build().fit(split.X_train, split.y_train)
    metrics = ModelEvaluator().evaluate(pipeline, split.X_test, split.y_test)
    assert set(metrics) == METRICS
    assert all(0.0 <= value <= 1.0 for value in metrics.values())


def test_trainer_logs_one_run_with_params_metrics_and_model(data):
    tracker = RecordingExperimentTracker()
    result = build_test_trainer(tracker).train(data, run_name="test", tags={"model_version": "1.2.3"})

    assert result.run_id == "run-1"
    assert len(tracker.runs) == 1
    run = tracker.runs[0]
    assert run.run_name == "test" and run.tags == {"model_version": "1.2.3"}
    assert run.metrics == result.metrics and set(run.metrics) == METRICS
    assert run.params["model_type"] == "LogisticRegression"
    assert run.params["feature_count"] == len(FEATURE_COLUMNS)
    assert run.estimator is result.pipeline
    assert list(run.input_example.columns) == list(FEATURE_COLUMNS)


def test_trainer_is_reproducible(data):
    first = build_test_trainer(RecordingExperimentTracker()).train(data)
    second = build_test_trainer(RecordingExperimentTracker()).train(data)
    assert first.metrics == second.metrics


def test_trainer_depends_on_injected_collaborators(data):
    class FixedEvaluator(ModelEvaluator):
        def evaluate(self, estimator, X_test, y_test):
            return {"accuracy": 1.0}

    trainer = ModelTrainer(PipelineFactory(), TrainTestSplitter(), FixedEvaluator(),
                           RecordingExperimentTracker())
    assert trainer.train(data).metrics == {"accuracy": 1.0}
