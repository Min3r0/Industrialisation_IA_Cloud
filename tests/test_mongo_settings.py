"""Configuration et connexion MongoDB (ADR-0011)."""
import pytest

from express_delivery.abstractions.order_repository import OrderSourceError
from express_delivery.config import MongoSettings
from express_delivery.infrastructure.mongo.connection import open_mongo_order_repository

SECRET_URI = "mongodb://lecteur:s3cret@mongodb:27017/?authSource=livraison_express"


def test_from_env_reads_every_variable(monkeypatch):
    monkeypatch.setenv("MONGO_URI", SECRET_URI)
    monkeypatch.setenv("MONGO_DATABASE", "analytics")
    monkeypatch.setenv("MONGO_COLLECTION", "orders_v2")
    monkeypatch.setenv("MONGO_TIMEOUT_MS", "1500")
    monkeypatch.setenv("MONGO_BATCH_SIZE", "200")
    assert MongoSettings.from_env() == MongoSettings(SECRET_URI, "analytics", "orders_v2", 1500, 200)


def test_defaults_target_the_erp_collection(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    settings = MongoSettings.from_env()
    assert (settings.database, settings.collection) == ("livraison_express", "orders")


def test_uri_is_mandatory(monkeypatch):
    monkeypatch.delenv("MONGO_URI", raising=False)
    with pytest.raises(ValueError, match="MONGO_URI"):
        MongoSettings.from_env()


@pytest.mark.parametrize("kwargs", [
    {"uri": "postgresql://livraison@localhost/livraison_express"},
    {"uri": "mongodb://localhost", "timeout_ms": 0},
    {"uri": "mongodb://localhost", "batch_size": 0},
])
def test_invalid_settings_are_rejected(kwargs):
    with pytest.raises(ValueError):
        MongoSettings(**kwargs)


def test_repr_never_shows_the_uri():
    assert "s3cret" not in repr(MongoSettings(SECRET_URI))


def test_unreachable_server_raises_order_source_error():
    # Port 1 : rien n'écoute, l'échec est immédiat (pas d'attente du délai complet)
    settings = MongoSettings("mongodb://127.0.0.1:1/?directConnection=true", timeout_ms=200)
    with pytest.raises(OrderSourceError, match="injoignable"):
        with open_mongo_order_repository(settings):
            pass  # pragma: no cover
