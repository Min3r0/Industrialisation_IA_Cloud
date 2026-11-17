"""Traduction d'une commande de l'ERP vers le vocabulaire du domaine (ADR-0012).

L'ERP et le modèle n'emploient pas les mêmes modalités (`suburb` / `banlieue`) ni la même
échelle de capacité du transporteur (5 à 50 / 0 à 1). Plutôt que de changer le contrat de
l'API (`openapi.yml`) et d'invalider le modèle 1.1.0, la différence est absorbée ici, à la
frontière, une seule fois (couche anticorruption).
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from express_delivery.domain.order_record import OrderRecord
from express_delivery.domain.order_validation import InvalidOrderError

# Capacité maximale observée dans l'ERP (simulateur : uniforme entre 5 et 50)
CARRIER_CAPACITY_MAX = 50.0

# `wind` n'a pas d'équivalent exact : il est rapproché de `orage` (météo dégradée sans
# précipitation franche). Approximation assumée et documentée dans l'ADR-0012.
MODALITY_MAP: Mapping[str, Mapping[str, str]] = MappingProxyType({
    "weather": MappingProxyType({"clear": "normal", "rain": "pluie", "snow": "neige", "wind": "orage"}),
    "delivery_zone": MappingProxyType({"centre": "centre", "suburb": "banlieue", "rural": "rurale"}),
    "customer_type": MappingProxyType({"individual": "standard", "business": "premium"}),
})


class ErpOrderTranslator:
    """Seule responsabilité : convertir une commande ERP validée en commande du domaine."""

    def translate(self, record: OrderRecord) -> OrderRecord:
        """Lève InvalidOrderError si une modalité ou la capacité sort des valeurs connues."""
        features = dict(record.features)
        for name, table in MODALITY_MAP.items():
            value = features[name]
            if value not in table:
                raise InvalidOrderError(
                    f"Commande {record.order_id!r} : {name}={value!r} sans équivalent dans le domaine"
                )
            features[name] = table[value]

        capacity = features["carrier_capacity"]
        if capacity > CARRIER_CAPACITY_MAX:
            raise InvalidOrderError(
                f"Commande {record.order_id!r} : carrier_capacity={capacity!r} dépasse {CARRIER_CAPACITY_MAX}"
            )
        features["carrier_capacity"] = round(capacity / CARRIER_CAPACITY_MAX, 4)
        return OrderRecord(order_id=record.order_id, order_date=record.order_date, features=features)
