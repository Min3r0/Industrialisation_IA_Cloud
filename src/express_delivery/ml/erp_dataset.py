"""Jeu d'entraînement construit à partir des commandes de l'ERP (ADR-0012).

Chaîne : commandes lues (`OrderRepository`) → traduction vers le domaine → étiquette
`express_eligible` calculée par la règle métier → DataFrame prêt pour `clean_orders_data`
et `validate_dataset`.
"""
from __future__ import annotations

import logging
from typing import Sequence

import pandas as pd

from express_delivery.domain.express_eligibility import ExpressEligibilityRule
from express_delivery.domain.features import TARGET_COLUMN
from express_delivery.domain.order_record import OrderRecord
from express_delivery.domain.order_translation import ErpOrderTranslator
from express_delivery.domain.order_validation import InvalidOrderError

logger = logging.getLogger(__name__)


class ErpTrainingDataBuilder:
    """Seule responsabilité : transformer des commandes ERP en jeu d'entraînement étiqueté."""

    def __init__(self, translator: ErpOrderTranslator, rule: ExpressEligibilityRule) -> None:
        self._translator = translator
        self._rule = rule

    def build(self, records: Sequence[OrderRecord]) -> pd.DataFrame:
        """Lève ValueError s'il n'y a aucune commande exploitable ou une seule classe."""
        rows = []
        rejected = 0
        for record in records:
            try:
                translated = self._translator.translate(record)
            except InvalidOrderError as error:
                rejected += 1
                logger.debug("Commande écartée : %s", error)
                continue
            rows.append({
                **translated.as_row(),
                TARGET_COLUMN: int(self._rule.is_eligible(translated.features)),
            })
        if rejected:
            logger.warning("%d commande(s) écartée(s) à la traduction ERP → domaine.", rejected)
        if not rows:
            raise ValueError("Aucune commande exploitable pour l'entraînement.")

        frame = pd.DataFrame(rows)
        if frame[TARGET_COLUMN].nunique() < 2:
            raise ValueError(
                "L'étiquette ne contient qu'une seule classe : entraînement impossible "
                "(vérifier la règle d'éligibilité ou la période)."
            )
        logger.info(
            "Jeu ERP : %d commandes, %.1f %% éligibles à l'express.",
            len(frame), 100 * frame[TARGET_COLUMN].mean(),
        )
        return frame
