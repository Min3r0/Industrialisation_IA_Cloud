"""Réentraîne le modèle sur les commandes récentes de l'ERP (orchestrateur, ADR-0013).

Composition root du réentraînement planifié : choisit la source (MongoDB, lecture seule),
la règle de déclenchement et la publication. La logique vit dans `ml/retraining.py`.

Usage :
    MONGO_URI=mongodb://localhost:27017 python scripts/retrain.py                 # une exécution
    MONGO_URI=... python scripts/retrain.py --every-hours 24                      # boucle planifiée
    Options : --window-days 30 --min-orders 500 --tracking --models-dir artifacts/models

Code de sortie : 0 si publié ou sauté (raison journalisée), 1 si la source ou la configuration échoue.
La version est `erp-AAAAMMJJ` : une seule publication par jour, les répétitions sont sans effet.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date
from pathlib import Path
from typing import Sequence

import sklearn

from express_delivery.abstractions.order_repository import OrderSourceError
from express_delivery.config import MongoSettings, Settings
from express_delivery.domain.express_eligibility import ExpressEligibilityRule
from express_delivery.domain.features import FEATURE_COLUMNS, TARGET_COLUMN
from express_delivery.domain.models import ModelMetadata
from express_delivery.domain.order_record import OrderRecord
from express_delivery.domain.order_translation import ErpOrderTranslator
from express_delivery.infrastructure.filesystem.model_repository import FileModelRepository
from express_delivery.infrastructure.mongo.connection import open_mongo_order_repository
from express_delivery.ml.dataset import clean_orders_data, validate_dataset
from express_delivery.ml.erp_dataset import ErpTrainingDataBuilder
from express_delivery.ml.pipeline_factory import PipelineFactory
from express_delivery.ml.retraining import RetrainingPipeline, RetrainingPolicy
from express_delivery.ml.training_setup import build_trainer, build_tracker

logger = logging.getLogger("retrain")


def make_publisher(settings: Settings, models_dir: Path, tracking: bool):
    """Publication : commandes → jeu étiqueté → entraînement → nouvelle version dans `models_dir`."""

    def publish(records: Sequence[OrderRecord], version: str) -> None:
        frame = ErpTrainingDataBuilder(ErpOrderTranslator(), ExpressEligibilityRule()).build(records)
        data = clean_orders_data(frame)
        validate_dataset(data)
        trainer = build_trainer(settings, build_tracker(settings, enabled=tracking))
        result = trainer.train(
            data,
            run_name=f"logistic-regression-{version}",
            tags={"model_version": version, "environment": settings.environment, "data_source": "erp-planifie"},
        )
        FileModelRepository(models_dir).save(result.pipeline, ModelMetadata(
            model_version=version,
            model_type=PipelineFactory.MODEL_TYPE,
            target=TARGET_COLUMN,
            features=FEATURE_COLUMNS,
            metrics=result.metrics,
            trained_at=date.today().isoformat(),
            sklearn_version=sklearn.__version__,
            mlflow_run_id=result.run_id,
        ))
        logger.info("Modèle %s publié (%d commandes).", version, len(data))

    return publish


def run_once(args: argparse.Namespace) -> int:
    """Une exécution du pipeline. Retourne le code de sortie du processus."""
    try:
        settings = Settings.from_env()
        models_dir = Path(args.models_dir)
        policy = RetrainingPolicy(freshness_window_days=args.window_days, min_recent_orders=args.min_orders)
        version = f"erp-{date.today():%Y%m%d}"
        models = FileModelRepository(models_dir)
        with open_mongo_order_repository(MongoSettings.from_env()) as repository:
            pipeline = RetrainingPipeline(
                repository=repository,
                publish=make_publisher(settings, models_dir, args.tracking),
                version_exists=models.exists,
                policy=policy,
            )
            outcome = pipeline.run(version)
    except (ValueError, OrderSourceError) as error:
        logger.error("Réentraînement impossible : %s", error)
        return 1
    logger.info("Résultat %s pour %s : %s", outcome.status, outcome.version, outcome.detail)
    return 0


def main() -> int:
    """Point d'entrée : une exécution, ou une boucle planifiée si --every-hours est donné."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models-dir", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--window-days", type=int, default=30, help="fenêtre de fraîcheur, en jours")
    parser.add_argument("--min-orders", type=int, default=500, help="commandes minimum dans la fenêtre")
    parser.add_argument("--tracking", action="store_true", help="enregistre chaque run dans MLflow")
    parser.add_argument("--every-hours", type=float, help="répète l'exécution toutes les N heures")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    if args.every_hours is None:
        return run_once(args)
    if args.every_hours <= 0:
        logger.error("--every-hours doit être strictement positif.")
        return 1
    while True:  # une erreur ponctuelle ne doit pas arrêter la planification
        run_once(args)
        time.sleep(args.every_hours * 3600)


if __name__ == "__main__":
    sys.exit(main())
