"""Vérifie la connexion à la base analytique MongoDB et résume les commandes lues (ADR-0011).

Composition root de la lecture des commandes, comme `train.py` pour l'entraînement.

Usage :
    MONGO_URI=mongodb://localhost:27017 python scripts/check_orders_source.py [--start 2023-01-01] [--end 2026-01-01]

Les documents rejetés par la validation sont comptés dans les logs (niveau WARNING),
le détail de chaque rejet est visible avec --verbose.
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import date

from express_delivery.abstractions.order_repository import OrderRepository, OrderSourceError
from express_delivery.config import MongoSettings
from express_delivery.domain.order_record import OrderPeriod
from express_delivery.infrastructure.mongo.connection import open_mongo_order_repository

logger = logging.getLogger("check_orders_source")


def summarize(repository: OrderRepository, period: OrderPeriod, sample_size: int) -> None:
    """Ne dépend que du port : fonctionne avec n'importe quelle implémentation."""
    records = repository.get_all(period)
    print(f"Commandes valides : {len(records)}")
    if not records:
        return
    dates = [record.order_date for record in records]
    print(f"Période couverte  : {min(dates)} → {max(dates)}")
    for name in ("weather", "delivery_zone", "customer_type"):
        print(f"{name:<17} : {dict(Counter(record.features[name] for record in records))}")
    for record in records[:sample_size]:
        print(record.as_row())


def main() -> int:
    """Retourne 0 si la base répond, 1 sinon (configuration absente ou serveur injoignable)."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, help="date de début incluse (AAAA-MM-JJ)")
    parser.add_argument("--end", type=date.fromisoformat, help="date de fin exclue (AAAA-MM-JJ)")
    parser.add_argument("--sample", type=int, default=3, help="nombre de commandes affichées")
    parser.add_argument("--verbose", action="store_true", help="détail de chaque document rejeté")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("pymongo").setLevel(logging.WARNING)

    try:
        settings = MongoSettings.from_env()
        period = OrderPeriod(args.start, args.end)
        with open_mongo_order_repository(settings) as repository:
            summarize(repository, period, args.sample)
    except (ValueError, OrderSourceError) as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
