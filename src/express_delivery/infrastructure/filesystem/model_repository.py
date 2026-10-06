"""Implémentation « répertoire local versionné » de ModelRepository (ADR-0002).

Disposition sur disque :

    <models_dir>/<version>/model.joblib     pipeline scikit-learn sérialisée
    <models_dir>/<version>/manifest.json    métadonnées + empreinte SHA-256 du modèle

joblib s'appuie sur pickle : charger un fichier modifié peut exécuter du code.
L'empreinte du manifeste est donc vérifiée avant tout chargement.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

import joblib
import sklearn

from express_delivery.abstractions.model_repository import (
    LoadedModel,
    ModelNotFoundError,
    ModelRepository,
)
from express_delivery.domain.models import ModelMetadata

logger = logging.getLogger(__name__)

MODEL_FILENAME = "model.joblib"
MANIFEST_FILENAME = "manifest.json"
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FileModelRepository(ModelRepository):
    def __init__(self, models_dir: Path) -> None:
        self._models_dir = models_dir

    def _version_dir(self, version: str) -> Path:
        if not _SEMVER.match(version):
            raise ModelNotFoundError(f"Version invalide (attendu X.Y.Z) : {version!r}")
        return self._models_dir / version

    def load(self, version: str) -> LoadedModel:
        version_dir = self._version_dir(version)
        model_path = version_dir / MODEL_FILENAME
        manifest_path = version_dir / MANIFEST_FILENAME
        if not model_path.is_file() or not manifest_path.is_file():
            raise ModelNotFoundError(f"Modèle {version} introuvable dans {version_dir}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if _sha256(model_path) != manifest.get("sha256"):
            raise ModelNotFoundError(f"Empreinte SHA-256 invalide pour le modèle {version}")

        metadata = ModelMetadata(
            model_version=manifest["model_version"],
            model_type=manifest["model_type"],
            target=manifest["target"],
            features=tuple(manifest["features"]),
            metrics=manifest["metrics"],
            trained_at=manifest["trained_at"],
            sklearn_version=manifest["sklearn_version"],
        )
        if metadata.sklearn_version != sklearn.__version__:
            logger.warning(
                "Modèle entraîné avec scikit-learn %s, exécuté avec %s",
                metadata.sklearn_version,
                sklearn.__version__,
            )
        return LoadedModel(estimator=joblib.load(model_path), metadata=metadata)

    def save(self, estimator: Any, metadata: ModelMetadata) -> None:
        version_dir = self._version_dir(metadata.model_version)
        if version_dir.exists():
            raise FileExistsError(
                f"La version {metadata.model_version} existe déjà : incrémentez MODEL_VERSION."
            )
        version_dir.mkdir(parents=True)
        model_path = version_dir / MODEL_FILENAME
        joblib.dump(estimator, model_path)

        manifest = asdict(metadata)
        manifest["features"] = list(metadata.features)
        manifest["sha256"] = _sha256(model_path)
        (version_dir / MANIFEST_FILENAME).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
