"""Objets métier de la sécurité d'accès (ADR-0006) : rôles et clés d'API.

Aucune clé en clair n'est manipulée ici : on ne stocke et ne compare que des
empreintes SHA-256 (la clé en clair n'est connue que du client).
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import date
from enum import IntEnum


class Role(IntEnum):
    """Rôles ordonnés : un rôle supérieur hérite des droits des rôles inférieurs."""

    GUEST = 1
    USER = 2
    ADMIN = 3

    @classmethod
    def parse(cls, value: str) -> "Role":
        try:
            return cls[value.strip().upper()]
        except KeyError as error:
            raise ValueError(f"Rôle inconnu : {value!r} (attendu : guest, user, admin)") from error


@dataclass(frozen=True)
class ApiKey:
    """Clé d'API enregistrée côté serveur (jamais la clé en clair)."""

    key_id: str
    key_hash: str
    role: Role
    expires_on: date

    def is_expired(self, today: date) -> bool:
        return today > self.expires_on

    def grants(self, required: Role) -> bool:
        return self.role >= required


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key(environment: str) -> str:
    """Clé aléatoire préfixée par l'environnement (ex. `sk_prod_…`), 192 bits d'entropie."""
    return f"sk_{environment}_{secrets.token_hex(24)}"
