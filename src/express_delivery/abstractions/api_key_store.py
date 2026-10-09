"""Port de lecture des clés d'API (ADR-0006).

En dev/test les clés viennent d'une variable d'environnement ; en production cette
variable est alimentée par une référence Azure Key Vault. Une autre source (base,
API Management…) = une nouvelle implémentation, sans toucher au service.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from express_delivery.domain.security import ApiKey


class ApiKeyStore(ABC):
    @abstractmethod
    def find_by_hash(self, key_hash: str) -> ApiKey | None:
        """Retourne la clé correspondant à l'empreinte, ou None si elle est inconnue."""
