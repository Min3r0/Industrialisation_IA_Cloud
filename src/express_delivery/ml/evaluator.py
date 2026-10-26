"""Évaluation d'un modèle entraîné sur le jeu de test (cellules 27 à 29 du notebook)."""
from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score


class ModelEvaluator:
    """Seule responsabilité : calculer les métriques de classification binaire."""

    def evaluate(self, estimator: Any, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, float]:
        y_pred = estimator.predict(X_test)
        y_proba = estimator.predict_proba(X_test)[:, 1]
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1_score": f1_score(y_test, y_pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, y_proba),
        }
        return {name: float(value) for name, value in metrics.items()}
