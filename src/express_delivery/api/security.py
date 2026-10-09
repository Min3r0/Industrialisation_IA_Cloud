"""Contrôle d'accès des routes métier : clé d'API, rôle, limitation du débit.

ADR-0005 (entrées/sorties) et ADR-0006 (accès à la donnée). Les sondes /health
restent publiques : l'orchestrateur doit pouvoir les appeler sans secret.
"""
from __future__ import annotations

from typing import Callable

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from express_delivery.api.dependencies import Container, get_container
from express_delivery.api.errors import ApiError
from express_delivery.domain.security import Role
from express_delivery.services.auth_service import AuthenticationError, AuthorizationError

API_KEY_HEADER = "X-API-Key"
_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False,
                               description="Clé d'API (ADR-0006). Obligatoire en production.")


def _identify(container: Container, request: Request, raw_key: str | None, required: Role) -> str:
    """Retourne l'identité utilisée pour le rate limiting (key_id, ou IP si auth désactivée)."""
    if container.auth_service is None:
        return f"ip:{request.client.host if request.client else 'unknown'}"
    try:
        key = container.auth_service.authenticate(raw_key)
        container.auth_service.authorize(key, required)
    except AuthenticationError as error:
        raise ApiError(401, "unauthorized", str(error)) from error
    except AuthorizationError as error:
        raise ApiError(403, "forbidden", str(error)) from error
    return f"key:{key.key_id}"


def require_role(required: Role) -> Callable[..., None]:
    """Dépendance FastAPI : authentifie, autorise puis applique la limite de débit."""

    def guard(request: Request, raw_key: str | None = Security(_api_key_header)) -> None:
        container = get_container(request)
        identity = _identify(container, request, raw_key, required)
        wait = container.rate_limiter.retry_after(identity)
        if wait:
            raise ApiError(429, "rate_limited", "Trop de requêtes, réessayez plus tard.",
                           headers={"Retry-After": str(wait)})

    return guard
