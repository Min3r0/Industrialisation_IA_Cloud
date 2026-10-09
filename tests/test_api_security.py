from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from express_delivery.api.app import create_app
from express_delivery.config import Settings
from express_delivery.domain.security import ApiKey, Role, hash_api_key
from express_delivery.infrastructure.env.api_key_store import format_api_key_entry
from express_delivery.infrastructure.memory.order_store import InMemoryOrderStore
from tests.conftest import EASY_ORDER, _settings

FUTURE = date.today() + timedelta(days=30)
KEYS = {"user": "sk_test_user", "guest": "sk_test_guest", "expired": "sk_test_expired"}
API_KEYS = ";".join(format_api_key_entry(key) for key in (
    ApiKey("front", hash_api_key(KEYS["user"]), Role.USER, FUTURE),
    ApiKey("visitor", hash_api_key(KEYS["guest"]), Role.GUEST, FUTURE),
    ApiKey("old", hash_api_key(KEYS["expired"]), Role.USER, date.today() - timedelta(days=1)),
))


def _client(models_dir, tmp_path, **overrides) -> TestClient:
    settings = _settings(models_dir, tmp_path, auth_enabled=True, api_keys=API_KEYS, **overrides)
    return TestClient(create_app(settings, order_store=InMemoryOrderStore()))


@pytest.fixture
def secured(models_dir, tmp_path):
    with _client(models_dir, tmp_path) as client:
        yield client


def _headers(name: str) -> dict:
    return {"X-API-Key": KEYS[name]}


def test_health_probes_stay_public(secured):
    assert secured.get("/health").status_code == 200
    assert secured.get("/health/ready").status_code == 200


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "sk_test_unknown"}, _headers("expired")])
def test_missing_invalid_or_expired_key_returns_401(secured, headers):
    response = secured.post("/v1/predictions", json=EASY_ORDER, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_insufficient_role_returns_403(secured):
    response = secured.get("/v1/orders/CMD-1", headers=_headers("guest"))
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


def test_valid_key_is_accepted(secured):
    assert secured.post("/v1/predictions", json=EASY_ORDER, headers=_headers("user")).status_code == 200


def test_rate_limit_returns_429_with_retry_after(models_dir, tmp_path):
    with _client(models_dir, tmp_path, rate_limit_per_minute=2) as client:
        for _ in range(2):
            assert client.get("/v1/orders/x", headers=_headers("user")).status_code == 404
        response = client.get("/v1/orders/x", headers=_headers("user"))
    assert response.status_code == 429
    assert response.json()["error"] == "rate_limited"
    assert int(response.headers["Retry-After"]) > 0


def test_docs_hidden_when_disabled(models_dir, tmp_path):
    with _client(models_dir, tmp_path, expose_docs=False) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_production_requires_authentication(models_dir, tmp_path):
    with pytest.raises(ValueError, match="AUTH_ENABLED"):
        Settings("prod", models_dir, "1.0.0", tmp_path / "o.db", 0.5, auth_enabled=False)


def test_production_defaults_are_secure(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    monkeypatch.delenv("EXPOSE_DOCS", raising=False)
    settings = Settings.from_env()
    assert settings.auth_enabled and not settings.expose_docs
