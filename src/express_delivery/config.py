"""Configuration de l'application, lue depuis les variables d'environnement.

Une seule source de vérité pour tout ce qui change d'un environnement à l'autre
(dev -> test -> prod) : aucun chemin, seuil ni secret n'est codé en dur ailleurs.
En production (Azure Container Apps, ADR-0003), les secrets (`API_KEYS`) sont des
références Azure Key Vault injectées comme variables d'environnement (ADR-0006).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PRODUCTION = "prod"
_TRUE = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in _TRUE


@dataclass(frozen=True)
class Settings:
    environment: str
    models_dir: Path
    model_version: str
    database_path: Path
    prediction_threshold: float
    auth_enabled: bool = False
    api_keys: str = ""
    rate_limit_per_minute: int = 60
    expose_docs: bool = True
    # Entraînement (scripts/train.py) : graine et suivi MLflow (ADR-0007)
    random_seed: int = 42
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    mlflow_experiment: str = "livraison-express"

    def __post_init__(self) -> None:
        if not 0.0 <= self.prediction_threshold <= 1.0:
            raise ValueError("PREDICTION_THRESHOLD doit être compris entre 0 et 1.")
        if self.rate_limit_per_minute < 1:
            raise ValueError("RATE_LIMIT_PER_MINUTE doit être >= 1.")
        if self.environment == PRODUCTION and not self.auth_enabled:
            raise ValueError("AUTH_ENABLED est obligatoire en production (ADR-0006).")

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("APP_ENV", "dev")
        is_prod = environment == PRODUCTION
        return cls(
            environment=environment,
            models_dir=Path(os.getenv("MODELS_DIR", "artifacts/models")),
            model_version=os.getenv("MODEL_VERSION", "1.0.0"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/orders.db")),
            prediction_threshold=float(os.getenv("PREDICTION_THRESHOLD", "0.5")),
            auth_enabled=_env_flag("AUTH_ENABLED", default=is_prod),
            api_keys=os.getenv("API_KEYS", ""),
            rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
            expose_docs=_env_flag("EXPOSE_DOCS", default=not is_prod),
            random_seed=int(os.getenv("RANDOM_SEED", "42")),
            mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"),
            mlflow_experiment=os.getenv("MLFLOW_EXPERIMENT_NAME", "livraison-express"),
        )


@dataclass(frozen=True)
class MongoSettings:
    """Connexion à la base analytique des commandes (ADR-0011).

    Séparée de `Settings` : seuls l'entraînement et les scripts de données en ont
    besoin, pas l'API. `MONGO_URI` peut contenir un mot de passe : il vient d'une
    variable d'environnement (Key Vault en test/prod, ADR-0006), jamais du code.
    """

    uri: str
    database: str = "livraison_express"
    collection: str = "orders"
    timeout_ms: int = 5000
    batch_size: int = 1000

    def __post_init__(self) -> None:
        if not self.uri.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MONGO_URI doit commencer par mongodb:// ou mongodb+srv://.")
        if self.timeout_ms < 1 or self.batch_size < 1:
            raise ValueError("MONGO_TIMEOUT_MS et MONGO_BATCH_SIZE doivent être >= 1.")

    def __repr__(self) -> str:  # l'URI (et son éventuel mot de passe) ne doit jamais finir dans un log
        return f"MongoSettings(database={self.database!r}, collection={self.collection!r})"

    @classmethod
    def from_env(cls) -> "MongoSettings":
        """Lit MONGO_URI (obligatoire), MONGO_DATABASE, MONGO_COLLECTION, MONGO_TIMEOUT_MS, MONGO_BATCH_SIZE."""
        uri = os.getenv("MONGO_URI", "").strip()
        if not uri:
            raise ValueError("MONGO_URI est obligatoire pour lire les commandes (ADR-0011).")
        return cls(
            uri=uri,
            database=os.getenv("MONGO_DATABASE", "livraison_express"),
            collection=os.getenv("MONGO_COLLECTION", "orders"),
            timeout_ms=int(os.getenv("MONGO_TIMEOUT_MS", "5000")),
            batch_size=int(os.getenv("MONGO_BATCH_SIZE", "1000")),
        )
