"""Test d'intégration sur une vraie base MongoDB (simulateur ERP de tp4-bdd.zip).

Ignoré par défaut (et donc en CI). Pour le lancer, bases et simulateur démarrés :
    MONGO_TEST_URI=mongodb://localhost:27017 python -m pytest -m integration
"""
import os

import pytest

from express_delivery.config import MongoSettings
from express_delivery.domain.features import FEATURE_COLUMNS
from express_delivery.infrastructure.mongo.connection import open_mongo_order_repository

MONGO_TEST_URI = os.getenv("MONGO_TEST_URI")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not MONGO_TEST_URI, reason="MONGO_TEST_URI non défini : pas de MongoDB de test"),
]


@pytest.fixture(scope="module")
def repository():
    with open_mongo_order_repository(MongoSettings(MONGO_TEST_URI)) as repo:
        yield repo


def test_reads_the_simulator_orders(repository):
    records = repository.get_all()
    assert records, "Aucune commande : le simulateur ERP a-t-il tourné ?"
    assert all(record.order_id.startswith("ERP-") for record in records)
    assert all(set(record.features) == set(FEATURE_COLUMNS) for record in records)
    assert min(record.order_date for record in records).year >= 2023  # base analytique : depuis 2023


def test_get_returns_a_known_order(repository):
    first = repository.get_all()[0]
    assert repository.get(first.order_id) == first
