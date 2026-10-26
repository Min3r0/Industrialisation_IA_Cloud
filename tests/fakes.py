"""Doublures de test partagées."""
from __future__ import annotations

from express_delivery.abstractions.experiment_tracker import ExperimentTracker, TrainingRun


class RecordingExperimentTracker(ExperimentTracker):
    """Garde les runs en mémoire pour vérifier ce que l'entraînement a tracé."""

    def __init__(self) -> None:
        self.runs: list[TrainingRun] = []

    def log_run(self, run: TrainingRun) -> str:
        self.runs.append(run)
        return f"run-{len(self.runs)}"
