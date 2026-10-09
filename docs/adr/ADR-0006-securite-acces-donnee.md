---
title: ADR-0006 — Sécuriser l'accès à la donnée (clés d'API, rôles, secrets)
date: 2026-10-09
tags: [adr, architecture, securite, authentification, cle-api, key-vault, seance-2]
aliases: [ADR-0006, Accès à la donnée, Clé d'API, Authentification]
status: Accepté
---

# ADR-0006 — Sécuriser l'accès à la donnée (clés d'API, rôles, secrets)

**Status :** Accepté
**Date :** 09/10/2026
**Séance :** 2

## Contexte

L'API donne accès à des **données de commandes clients** (`GET /v1/orders/{order_id}`) et à un **modèle** qui est une propriété intellectuelle (prédictions à volonté = possibilité de le copier). Il faut :

- savoir **qui** appelle (authentification) et **ce qu'il a le droit de faire** (autorisation par rôle) ;
- gérer des secrets (clés, chaîne de connexion à la base) **sans jamais les écrire dans le code ni dans Git** ;
- protéger le code, le modèle et les logiciels utilisés.

Les clients de l'API sont des **applications** (site e-commerce, back-office logistique), pas des personnes : pas de formulaire de connexion.

## Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Utilisateur + mot de passe | Connu | Inadapté à des appels machine-à-machine ; mot de passe à stocker côté client |
| B. **Clé d'API par client + rôle**, empreinte stockée dans Key Vault | Simple pour les clients (un en-tête), lien clé ↔ client, expiration et rotation faciles | Une clé volée est utilisable jusqu'à sa révocation → expiration courte + HTTPS obligatoire |
| C. OAuth2 / OpenID Connect (Entra ID, jetons JWT) | Standard, jetons courts, identité forte | Nécessite un fournisseur d'identité et l'enregistrement de chaque client ; complexe pour la séance |

## Décision

**Option B**, implémentée dans l'application ; OAuth2 (option C) reste l'évolution naturelle si le nombre de clients grandit.

### Clés d'API

- Format : `sk_<env>_<48 caractères hexadécimaux>` (192 bits aléatoires, module `secrets`), préfixe d'environnement pour repérer une clé de test utilisée en prod. Générée par `python scripts/create_api_key.py --id <client> --role <rôle> --days <≤ 90> --env <env>`.
- Transmise dans l'en-tête **`X-API-Key`**, uniquement en HTTPS.
- Le serveur ne connaît **que l'empreinte SHA-256** de la clé : la clé en clair est affichée une fois à la création puis transmise au client par un canal sûr. Comparaison à temps constant (`hmac.compare_digest`).
- Chaque clé est liée à un **identifiant client** (`key_id`), un **rôle** et une **date d'expiration** : **90 jours maximum** (7 à 30 jours pour les clés de test).
- **Rotation avant expiration** : on ajoute la nouvelle entrée, le client bascule, on retire l'ancienne. Plusieurs clés peuvent coexister pour un même client pendant la rotation.
- Réponses : clé absente, inconnue ou expirée → **401** `unauthorized` ; rôle insuffisant → **403** `forbidden`.

### Rôles (moindre privilège)

| Rôle | Droits |
|---|---|
| `guest` | Sondes publiques uniquement (aucune route `/v1/*`) |
| `user` | `POST /v1/orders`, `GET /v1/orders/{id}`, `POST /v1/predictions` (puis batch et historique en séance 5) |
| `admin` | Tout `user` + futures opérations d'administration (modèle, séance 3) |

Les rôles sont hiérarchiques (`Role` est un `IntEnum`) ; la politique d'accès est déclarée à un seul endroit, le *composition root* (`api/app.py`).

### Secrets

- Variable `API_KEYS` = liste d'entrées `key_id:sha256:rôle:AAAA-MM-JJ` séparées par `;` — elle ne contient **que des empreintes** : la lire ne permet pas d'appeler l'API.
- En test/prod, `API_KEYS` et la connexion PostgreSQL sont des **secrets Azure Key Vault** référencés par Container Apps et lus grâce à l'**identité managée** de l'application. Aucun secret dans l'image Docker, dans `openapi.yml`, dans les logs ni dans Git.
- En dev, les variables peuvent venir d'un fichier `.env` **local, ignoré par Git** (`.gitignore`) ; on n'y met jamais de clé de production.
- Accès humains à Key Vault, à la base et au registre via **Entra ID + RBAC** (rôles Azure au plus juste), pas de comptes partagés.

### Propriété intellectuelle et logiciels

- Registre d'images **privé** (ACR) et partage Azure Files des modèles **privé, en lecture seule** pour l'application ; seules les prédictions sortent, jamais le fichier du modèle.
- Le modèle est vérifié par **SHA-256** avant chargement (ADR-0002) : un artefact altéré est refusé.
- Versions des dépendances fixées et surveillées (`pip-audit` / Dependabot à brancher dans la CI) ; versions logicielles non exposées en production (`/docs` désactivé).
- Chiffrement : TLS en transit, chiffrement au repos par défaut des services Azure ; région France Central (RGPD).

## Conséquences

- Nouveau code, découplé par abstractions (SOLID) : `domain/security.py` (`Role`, `ApiKey`), port `ApiKeyStore`, adaptateur `EnvApiKeyStore`, service `AuthService`, dépendance FastAPI `require_role` (`api/security.py`). Passer à une autre source de clés (API Management, base) = une nouvelle classe `ApiKeyStore`.
- `AUTH_ENABLED` vaut `true` par défaut quand `APP_ENV=prod` ; l'application refuse de démarrer en prod sans authentification.
- Les clients doivent gérer l'expiration : une alerte (séance 7) devra prévenir 15 jours avant l'échéance d'une clé.
- Les données de commandes ne sont pas cloisonnées par client (un `user` peut relire n'importe quel `order_id`) : acceptable tant que les clients sont internes ; sinon il faudra enregistrer le `key_id` propriétaire avec la commande.

Related: [ADR-0005 — Entrées/sorties](ADR-0005-securite-entrees-sorties.md) · [ADR-0003 — Hébergement](ADR-0003-hebergement-plateforme-deploiement.md) · [ADR-0002 — Artefacts du modèle](ADR-0002-stockage-artefacts-modele.md) · [Architecture](../architecture.md)
