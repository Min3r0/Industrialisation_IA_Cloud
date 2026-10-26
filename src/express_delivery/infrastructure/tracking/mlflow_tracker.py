"""Implémentation MLflow de ExperimentTracker (ADR-0007).

Un run MLflow par entraînement : paramètres, métriques, tags et modèle scikit-learn
(avec sa signature déduite de `input_example`). MLflow est importé à la construction,
pas au chargement du module : l'API, qui ne s'entraîne jamais, n'en a pas besoin.
"""
from __future__ import annotations

import logging

from express_delivery.abstractions.experiment_tracker import ExperimentTracker, TrainingRun

logger = logging.getLogger(__name__)

# skops (format de sérialisation par défaut de MLflow 3) refuse les types non déclarés.
_SKOPS_TRUSTED_TYPES = ["numpy.dtype"]


class MlflowExperimentTracker(ExperimentTracker):
    def __init__(self, tracking_uri: str, experiment_name: str) -> None:
        import mlflow

        self._mlflow = mlflow
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        logger.info("Suivi MLflow : %s (expérience %s)", tracking_uri, experiment_name)

    def log_run(self, run: TrainingRun) -> str:
        import mlflow.sklearn

        with self._mlflow.start_run(run_name=run.run_name) as active:
            self._mlflow.set_tags(dict(run.tags))
            self._mlflow.log_params(dict(run.params))
            self._mlflow.log_metrics(dict(run.metrics))
            mlflow.sklearn.log_model(
                run.estimator,
                name="model",
                input_example=run.input_example,
                skops_trusted_types=_SKOPS_TRUSTED_TYPES,
            )
            run_id = active.info.run_id
        logger.info("Run MLflow enregistré : %s", run_id)
        return run_id
