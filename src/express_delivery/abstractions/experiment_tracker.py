"""Port de suivi des expériences d'entraînement (ADR-0007).

L'entraînement publie ses paramètres, ses métriques et le modèle produit auprès d'un
outil de suivi. Le code ML ne dépend que de ce port : MLflow aujourd'hui, un autre
outil demain (ou aucun en test) sans toucher au `ModelTrainer`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class TrainingRun:
    """Ce qu'un entraînement transmet à l'outil de suivi."""

    run_name: str
    params: Mapping[str, Any]
    metrics: Mapping[str, float]
    estimator: Any
    input_example: Any = None  # quelques lignes d'entrée : MLflow en déduit la signature
    tags: Mapping[str, str] = field(default_factory=dict)


class ExperimentTracker(ABC):
    @abstractmethod
    def log_run(self, run: TrainingRun) -> str | None:
        """Enregistre un run. Retourne son identifiant, ou None si rien n'est suivi."""
