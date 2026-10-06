"""Configuration de l'application, lue depuis les variables d'environnement.

Une seule source de vérité pour tout ce qui change d'un environnement à l'autre
(dev -> test -> prod) : aucun chemin ni seuil n'est codé en dur ailleurs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    environment: str
    models_dir: Path
    model_version: str
    database_path: Path
    prediction_threshold: float

    @classmethod
    def from_env(cls) -> "Settings":
        threshold = float(os.getenv("PREDICTION_THRESHOLD", "0.5"))
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("PREDICTION_THRESHOLD doit être compris entre 0 et 1.")
        return cls(
            environment=os.getenv("APP_ENV", "dev"),
            models_dir=Path(os.getenv("MODELS_DIR", "artifacts/models")),
            model_version=os.getenv("MODEL_VERSION", "1.0.0"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/orders.db")),
            prediction_threshold=threshold,
        )
