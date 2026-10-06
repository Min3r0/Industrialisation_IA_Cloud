"""Port de chargement des artefacts du modèle (ADR-0002)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from express_delivery.domain.models import ModelMetadata


class ModelNotFoundError(Exception):
    """La version de modèle demandée est absente ou corrompue."""


@dataclass(frozen=True)
class LoadedModel:
    estimator: Any  # objet exposant predict_proba (pipeline scikit-learn)
    metadata: ModelMetadata


class ModelRepository(ABC):
    @abstractmethod
    def load(self, version: str) -> LoadedModel:
        """Charge une version explicite du modèle. Lève ModelNotFoundError."""

    @abstractmethod
    def save(self, estimator: Any, metadata: ModelMetadata) -> None:
        """Publie une nouvelle version (immuable : refuse d'écraser une version existante)."""
