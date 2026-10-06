"""Entraîne le modèle et publie une nouvelle version dans le dépôt de modèles.

Usage : python scripts/train.py [--version 1.0.0] [--models-dir artifacts/models]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import sklearn

from express_delivery.domain.features import FEATURE_COLUMNS, TARGET_COLUMN
from express_delivery.domain.models import ModelMetadata
from express_delivery.infrastructure.filesystem.model_repository import FileModelRepository
from express_delivery.ml.dataset import clean_orders_data, generate_orders_dataset, validate_dataset
from express_delivery.ml.training import train_and_evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--models-dir", type=Path, default=Path("artifacts/models"))
    args = parser.parse_args()

    data = clean_orders_data(generate_orders_dataset())
    validate_dataset(data)
    result = train_and_evaluate(data)

    metadata = ModelMetadata(
        model_version=args.version,
        model_type="Logistic regression",
        target=TARGET_COLUMN,
        features=FEATURE_COLUMNS,
        metrics=result.metrics,
        trained_at=datetime.now(timezone.utc).isoformat(),
        sklearn_version=sklearn.__version__,
    )
    FileModelRepository(args.models_dir).save(result.pipeline, metadata)
    print(f"Modèle {args.version} publié dans {args.models_dir / args.version}")
    print(json.dumps(result.metrics, indent=2))


if __name__ == "__main__":
    main()
