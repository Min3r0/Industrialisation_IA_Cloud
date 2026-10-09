"""Génère une clé d'API et l'entrée à ajouter au secret API_KEYS (ADR-0006).

La clé en clair est affichée UNE seule fois : la transmettre au client par un canal
sûr. Seule l'empreinte va dans Azure Key Vault (ou dans API_KEYS en dev).

Usage : python scripts/create_api_key.py --id front --role user [--days 90] [--env prod]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from express_delivery.domain.security import ApiKey, Role, generate_api_key, hash_api_key
from express_delivery.infrastructure.env.api_key_store import format_api_key_entry

MAX_DAYS = 90  # durée de vie maximale d'une clé (rotation obligatoire avant expiration)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True, help="Identifiant lisible du client (ex. front)")
    parser.add_argument("--role", default="user", choices=[role.name.lower() for role in Role])
    parser.add_argument("--days", type=int, default=MAX_DAYS, help=f"Validité en jours (1 à {MAX_DAYS})")
    parser.add_argument("--env", default="dev", help="Environnement, sert de préfixe à la clé")
    args = parser.parse_args()
    if not 1 <= args.days <= MAX_DAYS:
        parser.error(f"--days doit être compris entre 1 et {MAX_DAYS}.")

    raw_key = generate_api_key(args.env)
    expires_on = datetime.now(timezone.utc).date() + timedelta(days=args.days)
    key = ApiKey(args.id, hash_api_key(raw_key), Role.parse(args.role), expires_on)

    print(f"Clé d'API (à transmettre au client, non conservée) : {raw_key}")
    print(f"Entrée à ajouter au secret API_KEYS (séparateur ';') : {format_api_key_entry(key)}")


if __name__ == "__main__":
    main()
