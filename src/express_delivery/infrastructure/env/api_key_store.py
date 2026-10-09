"""Clés d'API lues dans une variable d'environnement (ADR-0006).

Format : entrées séparées par `;`, champs séparés par `:`
    <key_id>:<sha256 de la clé>:<rôle>:<date d'expiration AAAA-MM-JJ>
Exemple : `front:5e88…a3f1:user:2027-01-07;ops:9c1d…77b0:admin:2026-11-08`

La variable ne contient que des empreintes : la lire ne permet pas d'appeler l'API.
"""
from __future__ import annotations

from datetime import date

from express_delivery.abstractions.api_key_store import ApiKeyStore
from express_delivery.domain.security import ApiKey, Role

_FIELDS = 4


def parse_api_keys(raw: str) -> list[ApiKey]:
    keys = []
    for entry in filter(None, (part.strip() for part in raw.split(";"))):
        fields = entry.split(":")
        if len(fields) != _FIELDS:
            raise ValueError(f"Entrée API_KEYS invalide ({_FIELDS} champs attendus) : {fields[0]!r}")
        key_id, key_hash, role, expires_on = (field.strip() for field in fields)
        keys.append(ApiKey(key_id, key_hash.lower(), Role.parse(role), date.fromisoformat(expires_on)))
    return keys


def format_api_key_entry(key: ApiKey) -> str:
    """Inverse de parse_api_keys pour une clé : ligne à ajouter dans le secret API_KEYS."""
    return f"{key.key_id}:{key.key_hash}:{key.role.name.lower()}:{key.expires_on.isoformat()}"


class EnvApiKeyStore(ApiKeyStore):
    def __init__(self, raw: str) -> None:
        self._by_hash = {key.key_hash: key for key in parse_api_keys(raw)}

    def find_by_hash(self, key_hash: str) -> ApiKey | None:
        return self._by_hash.get(key_hash)
