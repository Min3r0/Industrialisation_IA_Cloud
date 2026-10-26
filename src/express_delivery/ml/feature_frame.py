"""Conversion commandes → DataFrame de variables du modèle (frontière avec scikit-learn).

Partagé par l'entraînement (TrainTestSplitter) et la prédiction (PredictionService) :
les deux construisent l'entrée du modèle de la même façon, dans le même ordre (DRY).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from express_delivery.domain.features import FEATURE_COLUMNS


def build_feature_frame(
    rows: Iterable[Mapping[str, Any]],
    columns: Sequence[str] = FEATURE_COLUMNS,
) -> pd.DataFrame:
    """Une ligne par commande, uniquement les variables du modèle (jamais order_id)."""
    columns = list(columns)
    return pd.DataFrame([{name: row[name] for name in columns} for row in rows], columns=columns)


def select_features(data: pd.DataFrame, columns: Sequence[str] = FEATURE_COLUMNS) -> pd.DataFrame:
    """Même sélection appliquée à un jeu de données déjà tabulaire."""
    return data[list(columns)]
