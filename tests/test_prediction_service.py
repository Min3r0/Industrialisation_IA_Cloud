from express_delivery.infrastructure.filesystem.model_repository import FileModelRepository
from express_delivery.services.prediction_service import PredictionService
from tests.conftest import EASY_ORDER, HARD_ORDER, VERSION


def _service(models_dir, threshold=0.5):
    return PredictionService(FileModelRepository(models_dir).load(VERSION), threshold)


def test_easy_order_is_eligible(models_dir):
    result = _service(models_dir).predict("CMD-1", EASY_ORDER)
    assert result.decision == "oui" and result.express_eligible is True
    assert result.model_version == VERSION


def test_hard_order_is_not_eligible(models_dir):
    result = _service(models_dir).predict("CMD-2", HARD_ORDER)
    assert result.decision == "non" and 0 <= result.probability < 0.5


def test_threshold_is_configurable(models_dir):
    assert _service(models_dir, threshold=1.0).predict("CMD-1", EASY_ORDER).decision == "non"
