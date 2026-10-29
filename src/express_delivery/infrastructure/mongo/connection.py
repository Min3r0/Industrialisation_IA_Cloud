"""Ouverture et fermeture de la connexion MongoDB (ADR-0011).

Seule responsabilité : le cycle de vie du `MongoClient`. Le dépôt reçoit une collection
déjà ouverte (inversion des dépendances) : il reste testable sans serveur.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from express_delivery.abstractions.order_repository import OrderSourceError
from express_delivery.config import MongoSettings
from express_delivery.infrastructure.mongo.order_repository import MongoOrderRepository

logger = logging.getLogger(__name__)

APP_NAME = "express-delivery"


@contextmanager
def open_mongo_order_repository(settings: MongoSettings) -> Iterator[MongoOrderRepository]:
    """Connexion vérifiée (ping) puis dépôt prêt à lire ; le client est fermé en sortie.

    Lève OrderSourceError si le serveur ne répond pas dans `timeout_ms`.
    """
    client: MongoClient = MongoClient(
        settings.uri,
        appname=APP_NAME,  # identifie l'application dans les logs du serveur
        serverSelectionTimeoutMS=settings.timeout_ms,
        connectTimeoutMS=settings.timeout_ms,
        retryWrites=False,  # l'application n'écrit jamais dans la base analytique
    )
    try:
        try:
            client.admin.command("ping")
        except PyMongoError as error:
            raise OrderSourceError(f"MongoDB injoignable : {error}") from error
        logger.info("Connecté à MongoDB : %s.%s", settings.database, settings.collection)
        collection = client[settings.database][settings.collection]
        yield MongoOrderRepository(collection, batch_size=settings.batch_size)
    finally:
        client.close()
