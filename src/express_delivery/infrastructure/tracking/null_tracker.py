"""ExperimentTracker qui ne suit rien : `scripts/train.py --no-tracking`."""
from __future__ import annotations

from express_delivery.abstractions.experiment_tracker import ExperimentTracker, TrainingRun


class NullExperimentTracker(ExperimentTracker):
    def log_run(self, run: TrainingRun) -> str | None:
        return None
