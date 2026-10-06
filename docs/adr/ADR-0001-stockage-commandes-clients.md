---
title: ADR-0001 — Où stocker les commandes clients
date: 2026-10-06
tags: [adr, architecture, stockage, commandes, seance-1]
aliases: [ADR-0001, OrderStore, Stockage des commandes]
status: Accepté
---

# ADR-0001 — Où stocker les commandes clients

**Status :** Accepté
**Date :** 06/10/2026
**Séance :** 1

## Contexte

L'endpoint `POST /v1/orders` du contrat [openapi.yml](../../openapi.yml) doit **persister** chaque commande reçue (via un `OrderStore`) puis répondre immédiatement `202` ; `GET /v1/orders/{order_id}` doit pouvoir la relire. La sonde `/health/ready` doit vérifier que ce stockage est joignable.

Caractéristiques du besoin :

- Une commande = un identifiant (`order_id`) + 12 variables (cellule 20 du notebook) + un statut + une date de création. Quelques centaines d'octets.
- Écritures fréquentes et unitaires, lectures par clé primaire. Pas de requêtes analytiques à ce stade.
- Contexte de cours : un seul processus API, exécuté sur le poste du développeur (environnement **dev**). Le passage test → prod viendra aux séances suivantes.
- Le notebook dédoublonne sur `order_id` en gardant la **dernière** occurrence (cellule 18) : la même règle doit s'appliquer à la collecte.
- À la séance 5, l'historique des prédictions (`GET /v1/predictions/{order_id}`) et le batch s'appuieront sur ces commandes.

## Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Mémoire / fichiers JSON | Aucune dépendance, trivial à coder | Données perdues au redémarrage (mémoire) ; pas d'écriture concurrente sûre ni de requête (JSON) |
| B. **SQLite** | Fichier unique, aucun service à installer, transactionnel (ACID), SQL standard, inclus dans Python | Un seul écrivain à la fois ; pas adapté à plusieurs instances de l'API sur des machines différentes |
| C. PostgreSQL (Docker ou managé) | Proche de la prod, concurrence et montée en charge, multi-instances | Un service à lancer, sécuriser, sauvegarder et superviser dès la séance 1 |
| D. NoSQL (MongoDB, DynamoDB…) | Schéma souple pour un document « commande » | Service supplémentaire ; le schéma est en fait fixe et contractuel (OpenAPI) |

## Décision

**Option B — SQLite**, derrière l'abstraction `OrderStore` (ABC).

- `src/express_delivery/abstractions/order_store.py` : le port `OrderStore` (`save`, `get`, `is_reachable`).
- `src/express_delivery/infrastructure/sqlite/order_store.py` : `SqliteOrderStore`, table `orders(order_id PK, features JSON, status, created_at)`, mode WAL, une connexion par opération.
- `src/express_delivery/infrastructure/memory/order_store.py` : `InMemoryOrderStore` pour les tests unitaires.
- Le chemin du fichier est configuré par la variable d'environnement `DATABASE_PATH` (défaut `data/orders.db`).
- Ré-enregistrer un `order_id` existant **remplace** la commande (`INSERT OR REPLACE`), comme `drop_duplicates(keep="last")` dans le notebook.

Pourquoi : c'est la solution la plus simple qui soit **réellement persistante et transactionnelle** (YAGNI), et le SQL rend la migration vers PostgreSQL mécanique. Grâce à l'inversion de dépendance, les services et l'API ne connaissent que `OrderStore` : changer de base = écrire une nouvelle classe et modifier une ligne dans `create_app`, sans toucher au reste (principe ouvert/fermé). La même suite de tests tourne sur les deux implémentations (substitution de Liskov).

Évolution probable vers l'**option C (PostgreSQL)** dès que l'API tourne sur plusieurs instances, ou au passage en environnement de test/prod (séances 2-3).

## Conséquences

- Le fichier `data/orders.db` ne doit pas être versionné dans Git (`.gitignore`).
- La base n'est pas partagée entre plusieurs machines : **une seule instance de l'API** tant que cette ADR est active.
- Les 12 variables sont stockées en JSON : ajouter une variable au modèle ne demande pas de migration de schéma, mais toute requête SQL sur une variable passera par `json_extract`.
- Pas de sauvegarde automatique : acceptable en dev (données synthétiques), **bloquant pour la prod**.
- Le jour où l'API passe en multi-instances, cette ADR devra être marquée « Status : Superseded by ADR-000X » et une nouvelle décision (PostgreSQL) écrite, avec une classe `PostgresOrderStore`.

Related: [ADR-0002 — Artefacts du modèle](ADR-0002-stockage-artefacts-modele.md) · [Architecture de l'application](../architecture.md)
