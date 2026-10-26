"""Orchestration d'un entraînement : découper, entraîner, évaluer, tracer (ADR-0007).

Le `ModelTrainer` ne sait ni construire la pipeline, ni découper, ni calculer les
métriques, ni parler à MLflow : il reçoit chaque collaborateur au constructeur
(inversion des dépendances) et se contente de les enchaîner.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Mapping

import pandas as pd
from sklearn.pipeline import Pipeline

from express_delivery.abstractions.experiment_tracker import ExperimentTracker, TrainingRun
from express_delivery.domain.features import FEATURE_COLUMNS
from express_delivery.ml.evaluator import ModelEvaluator
from express_delivery.ml.pipeline_factory import PipelineFactory
from express_delivery.ml.splitter import TrainTestSplitter

logger = logging.getLogger(__name__)

_INPUT_EXAMPLE_ROWS = 5


@dataclass(frozen=True)
class TrainingResult:
    pipeline: Pipeline
    metrics: dict[str, float]
    run_id: str | None = None  # identifiant du run de suivi (MLflow), None si non suivi


class ModelTrainer:
    def __init__(
        self,
        pipeline_factory: PipelineFactory,
        splitter: TrainTestSplitter,
        evaluator: ModelEvaluator,
        tracker: ExperimentTracker,
    ) -> None:
        self._pipeline_factory = pipeline_factory
        self._splitter = splitter
        self._evaluator = evaluator
        self._tracker = tracker

    def train(
        self,
        data: pd.DataFrame,
        run_name: str = "logistic-regression",
        tags: Mapping[str, str] | None = None,
    ) -> TrainingResult:
        started = time.perf_counter()
        split = self._splitter.split(data)
        logger.info("Split : %d lignes d'entraînement, %d de test", len(split.X_train), len(split.X_test))

        pipeline = self._pipeline_factory.build().fit(split.X_train, split.y_train)
        metrics = self._evaluator.evaluate(pipeline, split.X_test, split.y_test)
        logger.info("Métriques : %s", ", ".join(f"{k}={v:.4f}" for k, v in metrics.items()))

        run_id = self._tracker.log_run(TrainingRun(
            run_name=run_name,
            params={
                **self._pipeline_factory.params,
                **self._splitter.params,
                "feature_count": len(FEATURE_COLUMNS),
                "training_rows": len(split.X_train),
            },
            metrics=metrics,
            estimator=pipeline,
            input_example=split.X_train.head(_INPUT_EXAMPLE_ROWS),
            tags=dict(tags or {}),
        ))
        logger.info("Entraînement terminé en %.2f s (run=%s)", time.perf_counter() - started, run_id)
        return TrainingResult(pipeline=pipeline, metrics=metrics, run_id=run_id)
