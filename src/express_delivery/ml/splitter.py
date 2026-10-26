"""Découpage apprentissage / test stratifié (cellule 22 du notebook)."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import train_test_split

from express_delivery.domain.features import TARGET_COLUMN
from express_delivery.ml.feature_frame import select_features


@dataclass(frozen=True)
class DataSplit:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series


class TrainTestSplitter:
    """Seule responsabilité : séparer les variables de la cible, puis train / test."""

    def __init__(self, test_size: float = 0.20, random_state: int = 42) -> None:
        if not 0.0 < test_size < 1.0:
            raise ValueError("test_size doit être compris strictement entre 0 et 1.")
        self._test_size = test_size
        self._random_state = random_state

    @property
    def params(self) -> dict[str, object]:
        return {"test_size": self._test_size, "split_random_state": self._random_state}

    def split(self, data: pd.DataFrame) -> DataSplit:
        X = select_features(data)
        y = data[TARGET_COLUMN]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self._test_size, random_state=self._random_state, stratify=y
        )
        return DataSplit(X_train, X_test, y_train, y_test)
