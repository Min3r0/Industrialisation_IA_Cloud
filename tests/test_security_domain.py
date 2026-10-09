from datetime import date

import pytest

from express_delivery.domain.security import ApiKey, Role, generate_api_key, hash_api_key
from express_delivery.infrastructure.env.api_key_store import (
    EnvApiKeyStore, format_api_key_entry, parse_api_keys)
from express_delivery.infrastructure.memory.rate_limiter import SlidingWindowRateLimiter
from express_delivery.services.auth_service import AuthenticationError, AuthorizationError, AuthService

TODAY = date(2026, 10, 9)
RAW_KEY = "sk_test_secret"


def _key(role=Role.USER, expires_on=date(2026, 12, 31)) -> ApiKey:
    return ApiKey("front", hash_api_key(RAW_KEY), role, expires_on)


def _service(key: ApiKey) -> AuthService:
    return AuthService(EnvApiKeyStore(format_api_key_entry(key)), today=lambda: TODAY)


def test_roles_are_hierarchical():
    assert _key(Role.ADMIN).grants(Role.USER)
    assert not _key(Role.GUEST).grants(Role.USER)


def test_generated_keys_are_unique_and_prefixed():
    first, second = generate_api_key("prod"), generate_api_key("prod")
    assert first != second and first.startswith("sk_prod_")


def test_entry_roundtrip():
    key = _key()
    assert parse_api_keys(f" {format_api_key_entry(key)} ; ") == [key]


@pytest.mark.parametrize("raw", ["front:abc:user", "front:abc:root:2026-12-31", "front:abc:user:31/12/2026"])
def test_invalid_entries_are_rejected(raw):
    with pytest.raises(ValueError):
        parse_api_keys(raw)


def test_authenticate_valid_key():
    assert _service(_key()).authenticate(RAW_KEY).key_id == "front"


@pytest.mark.parametrize("raw_key", [None, "", "sk_test_wrong"])
def test_authenticate_rejects_missing_or_unknown_key(raw_key):
    with pytest.raises(AuthenticationError):
        _service(_key()).authenticate(raw_key)


def test_authenticate_rejects_expired_key():
    with pytest.raises(AuthenticationError, match="expirée"):
        _service(_key(expires_on=date(2026, 10, 8))).authenticate(RAW_KEY)


def test_authorize_rejects_insufficient_role():
    with pytest.raises(AuthorizationError):
        AuthService.authorize(_key(Role.GUEST), Role.USER)


def test_rate_limiter_sliding_window():
    now = [0.0]
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60, clock=lambda: now[0])
    assert limiter.retry_after("a") == 0 and limiter.retry_after("a") == 0
    assert limiter.retry_after("a") == 60          # 3e requête dans la fenêtre : refusée
    assert limiter.retry_after("b") == 0           # compteur par identité
    now[0] = 60.0
    assert limiter.retry_after("a") == 0           # fenêtre écoulée : de nouveau autorisée
