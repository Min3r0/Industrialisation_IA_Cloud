"""Données d'entraînement : génération, contrôle qualité, nettoyage (cellules 8, 14, 18).

Séance 4 : ces fonctions seront branchées sur une vraie source de données.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from express_delivery.domain.features import FEATURE_COLUMNS, TARGET_COLUMN

_ZONE_PENALTY = {"centre": 0, "proche_banlieue": 0.10, "banlieue": 0.25, "rurale": 0.45}
_WEATHER_PENALTY = {"normal": 0, "pluie": 0.10, "neige": 0.25, "orage": 0.30}


def generate_orders_dataset(n_rows: int = 6000, random_state: int = 42) -> pd.DataFrame:
    """Jeu de commandes synthétique, identique au notebook."""
    rng = np.random.default_rng(random_state)
    order_date = pd.date_range(start="2025-01-01", end="2025-12-31", periods=n_rows)
    day_of_week = pd.Series(order_date).dt.dayofweek.to_numpy()

    data = pd.DataFrame({
        "order_id": [f"CMD-{i:06d}" for i in range(1, n_rows + 1)],
        "order_date": order_date,
        "hour": rng.integers(7, 23, size=n_rows),
        "day_of_week": day_of_week,
        "weekend": (day_of_week >= 5).astype(int),
        "distance_km": np.round(rng.gamma(shape=2.0, scale=4.0, size=n_rows), 2),
        "order_value_eur": np.round(rng.uniform(10, 250, size=n_rows), 2),
        "weight_kg": np.round(rng.uniform(0.2, 25, size=n_rows), 2),
        "stock_available": rng.binomial(1, 0.85, size=n_rows),
        "preparation_time_min": np.round(rng.normal(25, 10, size=n_rows).clip(5, 90), 1),
        "carrier_capacity": np.round(rng.uniform(0.2, 1.0, size=n_rows), 2),
        "weather": rng.choice(list(_WEATHER_PENALTY), size=n_rows, p=[0.65, 0.20, 0.10, 0.05]),
        "delivery_zone": rng.choice(list(_ZONE_PENALTY), size=n_rows, p=[0.30, 0.30, 0.25, 0.15]),
        "customer_type": rng.choice(["standard", "premium"], size=n_rows, p=[0.80, 0.20]),
    })

    score = (
        2.5
        - 0.18 * data["distance_km"]
        - 0.035 * data["preparation_time_min"]
        - 0.035 * data["weight_kg"]
        - data["delivery_zone"].map(_ZONE_PENALTY)
        - data["weather"].map(_WEATHER_PENALTY)
        + 1.8 * data["stock_available"]
        + 1.3 * data["carrier_capacity"]
        + (data["customer_type"] == "premium").astype(int) * 0.15
        - 0.40 * data["weekend"]
        - 0.08 * np.maximum(data["hour"] - 18, 0)
    )
    data[TARGET_COLUMN] = rng.binomial(1, 1 / (1 + np.exp(-score)))
    return data


def validate_dataset(df: pd.DataFrame) -> None:
    """Lève ValueError si le jeu de données viole une règle de qualité."""
    required = {"order_id", *FEATURE_COLUMNS, TARGET_COLUMN}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes obligatoires absentes : {sorted(missing)}")

    rules = {
        "Des identifiants de commande sont dupliqués.": ~df["order_id"].duplicated().any(),
        "La variable cible contient des valeurs manquantes.": df[TARGET_COLUMN].notna().all(),
        "Certaines heures sont invalides.": df["hour"].between(0, 23).all(),
        "La distance ne peut pas être négative.": df["distance_km"].ge(0).all(),
        "Le poids ne peut pas être négatif.": df["weight_kg"].ge(0).all(),
        "Le temps de préparation ne peut pas être négatif.": df["preparation_time_min"].ge(0).all(),
        "La capacité du transporteur doit être comprise entre 0 et 1.": df["carrier_capacity"].between(0, 1).all(),
        "stock_available doit contenir uniquement 0 ou 1.": df["stock_available"].isin([0, 1]).all(),
    }
    for message, is_valid in rules.items():
        if not is_valid:
            raise ValueError(message)


def clean_orders_data(df: pd.DataFrame) -> pd.DataFrame:
    """Dédoublonne (dernière occurrence gagnante) et retire les lignes invalides."""
    cleaned = df.drop_duplicates(subset=["order_id"], keep="last").copy()
    cleaned["order_date"] = pd.to_datetime(cleaned["order_date"], errors="coerce")
    cleaned = cleaned.dropna(subset=[
        "order_id", "distance_km", "weight_kg", "stock_available",
        "preparation_time_min", "carrier_capacity", TARGET_COLUMN,
    ])
    mask = (
        cleaned["distance_km"].ge(0)
        & cleaned["weight_kg"].ge(0)
        & cleaned["preparation_time_min"].ge(0)
        & cleaned["carrier_capacity"].between(0, 1)
        & cleaned["stock_available"].isin([0, 1])
    )
    return cleaned[mask].reset_index(drop=True)
