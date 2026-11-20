"""Entraîne le modèle, trace le run dans MLflow et publie une nouvelle version.

Composition root de l'entraînement : seul endroit qui choisit les implémentations
concrètes (dépôt de modèles, outil de suivi), comme `api/app.py` pour le service.

Usage : python scripts/train.py [--version 1.0.0] [--models-dir artifacts/models] [--no-tracking]
                                [--source synthetic|erp] [--start AAAA-MM-JJ] [--end AAAA-MM-JJ]
Données : `synthetic` (défaut, jeu du notebook) ou `erp` (commandes lues dans MongoDB via
MONGO_URI, étiquette dérivée par la règle métier — ADR-0011 et ADR-0012).
Suivi : MLFLOW_TRACKING_URI (défaut sqlite:///mlflow.db), MLFLOW_EXPERIMENT_NAME, RANDOM_SEED.
Interface MLflow : mlflow ui --backend-store-uri sqlite:///mlflow.db
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import sklearn

from express_delivery.abstractions.order_repository import OrderSourceError
from express_delivery.config import MongoSettings, Settings
from express_delivery.domain.express_eligibility import ExpressEligibilityRule
from express_delivery.domain.features import FEATURE_COLUMNS, TARGET_COLUMN
from express_delivery.domain.models import ModelMetadata
from express_delivery.domain.order_record import OrderPeriod
from express_delivery.domain.order_translation import ErpOrderTranslator
from express_delivery.infrastructure.filesystem.model_repository import FileModelRepository
from express_delivery.ml.dataset import clean_orders_data, generate_orders_dataset, validate_dataset
from express_delivery.ml.erp_dataset import ErpTrainingDataBuilder
from express_delivery.ml.pipeline_factory import PipelineFactory
from express_delivery.ml.training_setup import build_trainer, build_tracker

logger = logging.getLogger("train")


def load_synthetic_data(settings: Settings) -> pd.DataFrame:
    """Jeu synthétique du notebook (comportement historique)."""
    return generate_orders_dataset(random_state=settings.random_seed)


def load_erp_data(period: OrderPeriod) -> pd.DataFrame:
    """Commandes de l'ERP lues en lecture seule dans MongoDB, étiquetées par la règle métier."""
    # Import paresseux voulu : pymongo n'est requis que pour lire l'ERP (extra `mongo`, ADR-0011)
    # pylint: disable-next=import-outside-toplevel
    from express_delivery.infrastructure.mongo.connection import open_mongo_order_repository

    with open_mongo_order_repository(MongoSettings.from_env()) as repository:
        records = repository.get_all(period)
    builder = ErpTrainingDataBuilder(ErpOrderTranslator(), ExpressEligibilityRule())
    return builder.build(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--models-dir", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--no-tracking", action="store_true", help="N'enregistre pas le run dans MLflow")
    parser.add_argument("--source", choices=("synthetic", "erp"), default="synthetic",
                        help="origine des données d'entraînement (défaut : synthetic)")
    parser.add_argument("--start", type=date.fromisoformat, help="--source erp : date de début incluse (AAAA-MM-JJ)")
    parser.add_argument("--end", type=date.fromisoformat, help="--source erp : date de fin exclue (AAAA-MM-JJ)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    settings = Settings.from_env()
    repository = FileModelRepository(args.models_dir)
    if repository.exists(args.version):  # avant d'entraîner : pas de run MLflow orphelin
        logger.error("La version %s existe déjà : incrémentez --version (ADR-0002).", args.version)
        return 1

    try:
        if args.source == "erp":
            raw = load_erp_data(OrderPeriod(args.start, args.end))
        else:
            raw = load_synthetic_data(settings)
        data = clean_orders_data(raw)
        validate_dataset(data)
    except (ValueError, OrderSourceError) as error:  # config absente, source injoignable, données inutilisables
        logger.error("%s", error)
        return 1
    logger.info("Source des données : %s (%d lignes)", args.source, len(data))

    trainer = build_trainer(settings, build_tracker(settings, enabled=not args.no_tracking))
    result = trainer.train(
        data,
        run_name=f"logistic-regression-{args.version}",
        tags={"model_version": args.version, "environment": settings.environment, "data_source": args.source},
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
