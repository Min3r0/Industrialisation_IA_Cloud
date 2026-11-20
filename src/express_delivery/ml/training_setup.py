"""Assemblage d'un entraîneur et de son outil de suivi (ADR-0007, ADR-0013).

Partagé par les scripts qui entraînent un modèle (`scripts/train.py`, `scripts/retrain.py`) :
seul le choix des implémentations concrètes reste dans chaque script.
"""
from __future__ import annotations

import logging

from express_delivery.abstractions.experiment_tracker import ExperimentTracker
from express_delivery.config import Settings
from express_delivery.infrastructure.tracking.null_tracker import NullExperimentTracker
from express_delivery.ml.evaluator import ModelEvaluator
from express_delivery.ml.pipeline_factory import PipelineFactory
from express_delivery.ml.splitter import TrainTestSplitter
from express_delivery.ml.trainer import ModelTrainer

logger = logging.getLogger(__name__)


def build_tracker(settings: Settings, enabled: bool) -> ExperimentTracker:
    """Suivi MLflow si `enabled`, sinon suivi nul. MLflow n'est importé que si nécessaire (ADR-0007)."""
    if not enabled:
        logger.warning("Suivi MLflow désactivé.")
        return NullExperimentTracker()
    # pylint: disable-next=import-outside-toplevel
    from express_delivery.infrastructure.tracking.mlflow_tracker import MlflowExperimentTracker

    return MlflowExperimentTracker(settings.mlflow_tracking_uri, settings.mlflow_experiment)


def build_trainer(settings: Settings, tracker: ExperimentTracker) -> ModelTrainer:
    """Entraîneur avec les réglages du projet (graine, 20 % de test)."""
    return ModelTrainer(
        pipeline_factory=PipelineFactory(random_state=settings.random_seed),
        splitter=TrainTestSplitter(test_size=0.20, random_state=settings.random_seed),
        evaluator=ModelEvaluator(),
        tracker=tracker,
    )
