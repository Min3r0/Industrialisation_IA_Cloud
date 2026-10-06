"""Ajuste le schéma généré par FastAPI pour qu'il corresponde au contrat openapi.yml.

FastAPI ajoute d'office une réponse 422 `HTTPValidationError` sur toute route qui a
des paramètres. Nos erreurs de validation sortent au format `Error` (voir errors.py) :
les 422 automatiques sont donc retirées ; celles déclarées explicitement sont gardées.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

_AUTO_SCHEMA = "#/components/schemas/HTTPValidationError"


def install_contract_openapi(app: FastAPI) -> None:
    def contract_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version,
                             description=app.description, routes=app.routes)
        for item in schema["paths"].values():
            for operation in item.values():
                auto = operation["responses"].get("422", {})
                if _AUTO_SCHEMA in str(auto):
                    del operation["responses"]["422"]
        for name in ("HTTPValidationError", "ValidationError"):
            schema.get("components", {}).get("schemas", {}).pop(name, None)
        app.openapi_schema = schema
        return schema

    app.openapi = contract_openapi
