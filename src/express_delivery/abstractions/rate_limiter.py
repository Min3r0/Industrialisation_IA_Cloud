"""Port de limitation du débit (ADR-0005)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class RateLimiter(ABC):
    @abstractmethod
    def retry_after(self, identity: str) -> int:
        """Enregistre une requête de `identity`.

        Retourne 0 si elle est autorisée, sinon le nombre de secondes à attendre.
        """
