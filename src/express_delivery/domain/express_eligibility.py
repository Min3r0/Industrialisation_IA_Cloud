"""Règle métier d'éligibilité à la livraison express (ADR-0012).

Les commandes de l'ERP ne contiennent pas la cible `express_eligible` (ADR-0011) : elle est
dérivée ici, à partir des variables de la commande, par des critères d'exploitation
explicites. Les seuils sont des hypothèses métier à faire valider ; ils vivent dans
`EligibilityCriteria` (un seul endroit à modifier) et non dans le code de la règle.

La règle s'applique à une commande exprimée avec les modalités du domaine
(voir `order_translation.py`), jamais avec celles de l'ERP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

_DEFAULT_MAX_DISTANCE_KM: Mapping[str, float] = MappingProxyType({
    "centre": 35.0,
    "proche_banlieue": 30.0,
    "banlieue": 30.0,
    "rurale": 20.0,
})


@dataclass(frozen=True)
class EligibilityCriteria:
    """Seuils d'exploitation d'une livraison express (hypothèses métier, ADR-0012)."""

    max_preparation_min: float = 35.0
    last_order_hour: int = 17  # dernière heure de commande acceptée (départ du dernier coursier à 18 h)
    max_weight_kg: float = 20.0  # colis transportable par un coursier
    excluded_weather: frozenset[str] = frozenset({"neige"})
    max_distance_km: Mapping[str, float] = field(default_factory=lambda: _DEFAULT_MAX_DISTANCE_KM)


class ExpressEligibilityRule:
    """Seule responsabilité : dire si une commande peut être livrée en express, et pourquoi pas."""

    def __init__(self, criteria: EligibilityCriteria | None = None) -> None:
        self._criteria = criteria or EligibilityCriteria()

    def failed_criteria(self, features: Mapping[str, Any]) -> list[str]:
        """Noms des critères non satisfaits (vide si la commande est éligible).

        Lève ValueError si la zone de livraison est inconnue : mieux vaut refuser d'étiqueter
        que d'inventer une étiquette.
        """
        criteria = self._criteria
        zone = features["delivery_zone"]
        if zone not in criteria.max_distance_km:
            raise ValueError(f"Zone de livraison inconnue : {zone!r}")
        checks = {
            "stock_indisponible": features["stock_available"] != 1,
            "preparation_trop_longue": features["preparation_time_min"] > criteria.max_preparation_min,
            "commande_trop_tardive": features["hour"] > criteria.last_order_hour,
            "colis_trop_lourd": features["weight_kg"] > criteria.max_weight_kg,
            "meteo_excluante": features["weather"] in criteria.excluded_weather,
            "distance_trop_grande": features["distance_km"] > criteria.max_distance_km[zone],
        }
        return [name for name, failed in checks.items() if failed]

    def is_eligible(self, features: Mapping[str, Any]) -> bool:
        """Vrai si aucun critère n'est violé."""
        return not self.failed_criteria(features)
