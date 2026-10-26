"""Entraîne le modèle, trace le run dans MLflow et publie une nouvelle version.

Composition root de l'entraînement : seul endroit qui choisit les implémentations
concrètes (dépôt de modèles, outil de suivi), comme `api/app.py` pour le service.

Usage : python scripts/train.py [--version 1.0.0] [--models-dir artifacts/models] [--no-tracking]
Suivi : MLFLOW_TRACKING_URI (défaut sqlite:///mlflow.db), MLFLOW_EXPERIMENT_NAME, RANDOM_SEED.
Interface MLflow : mlflow ui --backend-store-uri sqlite:///mlflow.db
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import sklearn

from express_delivery.abstractions.experiment_tracker import ExperimentTracker
from express_delivery.config import Settings
from express_delivery.domain.features import FEATURE_COLUMNS, TARGET_COLUMN
from express_delivery.domain.models import ModelMetadata
from express_delivery.infrastructure.filesystem.model_repository import FileModelRepository
from express_delivery.infrastructure.tracking.null_tracker import NullExperimentTracker
from express_delivery.ml.dataset import clean_orders_data, generate_orders_dataset, validate_dataset
from express_delivery.ml.evaluator import ModelEvaluator
from express_delivery.ml.pipeline_factory import PipelineFactory
from express_delivery.ml.splitter import TrainTestSplitter
from express_delivery.ml.trainer import ModelTrainer

logger = logging.getLogger("train")


def build_tracker(settings: Settings, enabled: bool) -> ExperimentTracker:
    if not enabled:
        logger.warning("Suivi MLflow désactivé (--no-tracking).")
        return NullExperimentTracker()
    from express_delivery.infrastructure.tracking.mlflow_tracker import MlflowExperimentTracker

    return MlflowExperimentTracker(settings.mlflow_tracking_uri, settings.mlflow_experiment)


def build_trainer(settings: Settings, tracker: ExperimentTracker) -> ModelTrainer:
    return ModelTrainer(
        pipeline_factory=PipelineFactory(random_state=settings.random_seed),
        splitter=TrainTestSplitter(test_size=0.20, random_state=settings.random_seed),
        evaluator=ModelEvaluator(),
        tracker=tracker,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--models-dir", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--no-tracking", action="store_true", help="N'enregistre pas le run dans MLflow")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    settings = Settings.from_env()
    repository = FileModelRepository(args.models_dir)
    if repository.exists(args.version):  # avant d'entraîner : pas de run MLflow orphelin
        logger.error("La version %s existe déjà : incrémentez --version (ADR-0002).", args.version)
        return 1

    data = clean_orders_data(generate_orders_dataset(random_state=settings.random_seed))
    validate_dataset(data)

    trainer = build_trainer(settings, build_tracker(settings, enabled=not args.no_tracking))
    result = trainer.train(
        data,
        run_name=f"logistic-regression-{args.version}",
        tags={"model_version": args.version, "environment": settings.environment},
    )

    repository.save(result.pipeline, ModelMetadata(
        model_version=args.version,
        model_type=PipelineFactory.MODEL_TYPE,
        target=TARGET_COLUMN,
        features=FEATURE_COLUMNS,
        metrics=result.metrics,
        trained_at=datetime.now(timezone.utc).isoformat(),
        sklearn_version=sklearn.__version__,
        mlflow_run_id=result.run_id,
    ))
    print(f"Modèle {args.version} publié dans {args.models_dir / args.version} (run MLflow : {result.run_id})")
    print(json.dumps(result.metrics, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
