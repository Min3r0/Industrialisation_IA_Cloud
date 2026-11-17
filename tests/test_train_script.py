"""Composition root de l'entraînement (`scripts/train.py`) : choix de la source de données."""
import json
import sys

import pytest

from express_delivery.abstractions.order_repository import OrderSourceError
from express_delivery.domain.express_eligibility import ExpressEligibilityRule
from express_delivery.domain.order_translation import ErpOrderTranslator
from express_delivery.ml.erp_dataset import ErpTrainingDataBuilder
from scripts import train
from tests.erp_orders import simulated_erp_records


def _run(monkeypatch, tmp_path, *arguments) -> int:
    command = ["train.py", "--models-dir", str(tmp_path / "models"), "--no-tracking", *arguments]
    monkeypatch.setattr(sys, "argv", command)
    return train.main()


def test_erp_source_publishes_a_model_tagged_with_its_data(monkeypatch, tmp_path, capsys):
    builder = ErpTrainingDataBuilder(ErpOrderTranslator(), ExpressEligibilityRule())
    monkeypatch.setattr(train, "load_erp_data", lambda period: builder.build(simulated_erp_records(1500)))

    assert _run(monkeypatch, tmp_path, "--source", "erp", "--version", "2.0.0") == 0

    metadata = json.loads((tmp_path / "models" / "2.0.0" / "manifest.json").read_text(encoding="utf-8"))
    assert metadata["model_version"] == "2.0.0"
    assert "Modèle 2.0.0 publié" in capsys.readouterr().out


@pytest.mark.parametrize("error", [OrderSourceError("MongoDB injoignable"), ValueError("MONGO_URI est obligatoire")])
def test_unavailable_erp_source_fails_cleanly_without_publishing(monkeypatch, tmp_path, error):
    def failing_loader(_period):
        raise error

    monkeypatch.setattr(train, "load_erp_data", failing_loader)
    assert _run(monkeypatch, tmp_path, "--source", "erp", "--version", "2.0.0") == 1
    assert not (tmp_path / "models" / "2.0.0").exists()


def test_synthetic_source_remains_the_default(monkeypatch, tmp_path):
    monkeypatch.setattr(train, "load_erp_data", lambda period: pytest.fail("l'ERP ne doit pas être lu par défaut"))
    assert _run(monkeypatch, tmp_path, "--version", "1.0.1") == 0
