"""Cas d'usage : authentifier une clé d'API et vérifier le rôle (ADR-0006)."""
from __future__ import annotations

import hmac
from datetime import date, datetime, timezone
from typing import Callable

from express_delivery.abstractions.api_key_store import ApiKeyStore
from express_delivery.domain.security import ApiKey, Role, hash_api_key


class AuthenticationError(Exception):
    """Clé absente, inconnue ou expirée (HTTP 401)."""


class AuthorizationError(Exception):
    """Clé valide mais rôle insuffisant (HTTP 403)."""


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


class AuthService:
    def __init__(self, store: ApiKeyStore, today: Callable[[], date] = _today_utc) -> None:
        self._store = store
        self._today = today

    def authenticate(self, raw_key: str | None) -> ApiKey:
        if not raw_key:
            raise AuthenticationError("Clé d'API manquante (en-tête X-API-Key).")
        key_hash = hash_api_key(raw_key)
        key = self._store.find_by_hash(key_hash)
        # compare_digest : comparaison à temps constant (pas de fuite par le temps de réponse)
        if key is None or not hmac.compare_digest(key.key_hash, key_hash):
            raise AuthenticationError("Clé d'API invalide.")
        if key.is_expired(self._today()):
            raise AuthenticationError("Clé d'API expirée : demandez une rotation.")
        return key

    @staticmethod
    def authorize(key: ApiKey, required: Role) -> None:
        if not key.grants(required):
            raise AuthorizationError(f"Rôle « {required.name.lower()} » requis.")
