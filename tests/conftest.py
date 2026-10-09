from __future__ import annotations

from pathlib import Path

import pytest
import sklearn
from fastapi.testclient import TestClient

from express_delivery.api.app import create_app
from express_delivery.config import Settings
from express_delivery.domain.features import FEATURE_COLUMNS, TARGET_COLUMN
from express_delivery.domain.models import ModelMetadata
from express_delivery.infrastructure.filesystem.model_repository import FileModelRepository
from express_delivery.infrastructure.memory.order_store import InMemoryOrderStore
from express_delivery.ml.dataset import clean_orders_data, generate_orders_dataset
from express_delivery.ml.training import train_and_evaluate

VERSION = "1.0.0"

# Commandes d'exemple des cellules 37 et 38 du notebook
EASY_ORDER = {
    "hour": 14, "day_of_week": 2, "weekend": 0, "distance_km": 3.5,
    "order_value_eur": 89.90, "weight_kg": 2.4, "stock_available": 1,
    "preparation_time_min": 18, "carrier_capacity": 0.85,
    "weather": "normal", "delivery_zone": "centre", "customer_type": "premium",
}
HARD_ORDER = {
    "hour": 21, "day_of_week": 6, "weekend": 1, "distance_km": 28,
    "order_value_eur": 25.00, "weight_kg": 18, "stock_available": 0,
    "preparation_time_min": 70, "carrier_capacity": 0.25,
    "weather": "orage", "delivery_zone": "rurale", "customer_type": "standard",
}


@pytest.fixture(scope="session")
def models_dir(tmp_path_factory) -> Path:
    directory = tmp_path_factory.mktemp("models")
    result = train_and_evaluate(clean_orders_data(generate_orders_dataset(n_rows=2000)))
    FileModelRepository(directory).save(
        result.pipeline,
        ModelMetadata(VERSION, "Logistic regression", TARGET_COLUMN, FEATURE_COLUMNS,
                      result.metrics, "2026-10-06T00:00:00+00:00", sklearn.__version__),
    )
    return directory


def _settings(models_dir: Path, tmp_path: Path, version: str = VERSION, **overrides) -> Settings:
    return Settings("test", models_dir, version, tmp_path / "orders.db", 0.5, **overrides)


@pytest.fixture
def client(models_dir, tmp_path):
    app = create_app(_settings(models_dir, tmp_path), order_store=InMemoryOrderStore())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_without_model(models_dir, tmp_path):
    app = create_app(_settings(models_dir, tmp_path, "9.9.9"), order_store=InMemoryOrderStore())
    with TestClient(app) as test_client:
        yield test_client
