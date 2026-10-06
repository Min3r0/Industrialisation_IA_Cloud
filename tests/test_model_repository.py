import pytest

from express_delivery.abstractions.model_repository import ModelNotFoundError
from express_delivery.infrastructure.filesystem.model_repository import (
    MODEL_FILENAME,
    FileModelRepository,
)
from tests.conftest import VERSION


def test_load_returns_estimator_and_metadata(models_dir):
    model = FileModelRepository(models_dir).load(VERSION)
    assert model.metadata.model_version == VERSION
    assert hasattr(model.estimator, "predict_proba")


def test_unknown_version_raises(models_dir):
    with pytest.raises(ModelNotFoundError):
        FileModelRepository(models_dir).load("2.0.0")


def test_invalid_version_format_raises(models_dir):
    with pytest.raises(ModelNotFoundError):
        FileModelRepository(models_dir).load("../etc")


def test_existing_version_is_immutable(models_dir):
    repository = FileModelRepository(models_dir)
    loaded = repository.load(VERSION)
    with pytest.raises(FileExistsError):
        repository.save(loaded.estimator, loaded.metadata)


def test_tampered_model_is_rejected(models_dir, tmp_path):
    import shutil
    copy = tmp_path / "models"
    shutil.copytree(models_dir, copy)
    with open(copy / VERSION / MODEL_FILENAME, "ab") as file:
        file.write(b"tampered")
    with pytest.raises(ModelNotFoundError, match="SHA-256"):
        FileModelRepository(copy).load(VERSION)
