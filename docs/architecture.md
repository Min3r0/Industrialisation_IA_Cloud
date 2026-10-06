---
title: Architecture de l'application (notebook → API)
date: 2026-10-06
tags: [architecture, solid, clean-code, fastapi, seance-1]
aliases: [Architecture]
---

# Architecture de l'application (notebook → API)

Transformation du notebook `project_test_v1_final_final2.ipynb` en application FastAPI respectant le contrat [openapi.yml](../openapi.yml) (opérations `x-session: 1`).

## Vue d'ensemble

```mermaid
flowchart LR
    Client -->|HTTP| API[api/routers<br/>health · orders · predictions]
    API --> OS[services/OrderService]
    API --> PS[services/PredictionService]
    OS --> OSP{{abstractions/OrderStore}}
    PS --> LM[LoadedModel]
    APP[api/app.py<br/>composition root] --> MRP{{abstractions/ModelRepository}}
    MRP --> LM
    OSP -.implémente.- SQL[infrastructure/sqlite<br/>SqliteOrderStore]
    OSP -.implémente.- MEM[infrastructure/memory<br/>InMemoryOrderStore]
    MRP -.implémente.- FS[infrastructure/filesystem<br/>FileModelRepository]
    TRAIN[scripts/train.py] --> ML[ml/dataset + ml/training]
    TRAIN --> MRP
```

## Arborescence

```text
src/express_delivery/
├── config.py                  # Settings lus depuis l'environnement (dev/test/prod)
├── domain/                    # Objets métier purs : Order, PredictionResult, ModelMetadata, FEATURE_COLUMNS
├── abstractions/              # Ports (ABC) : OrderStore, ModelRepository
├── infrastructure/            # Adaptateurs concrets
│   ├── sqlite/                #   SqliteOrderStore        → ADR-0001
│   ├── memory/                #   InMemoryOrderStore (tests)
│   └── filesystem/            #   FileModelRepository     → ADR-0002
├── ml/                        # Données et entraînement (cellules 8 à 29 du notebook)
├── services/                  # Cas d'usage : OrderService, PredictionService (cellule 34)
└── api/                       # FastAPI : schémas, erreurs, routes, composition root
scripts/train.py               # Entraîne et publie une version de modèle
tests/                         # 34 tests dont la vérification du contrat OpenAPI
```

## Correspondance notebook → application

| Cellule(s) | Élément du notebook | Module de l'application |
|---|---|---|
| 3, 5 | Constantes, `ARTIFACTS_DIR`, `MODEL_VERSION` | `config.py` (variables d'environnement) |
| 8 | `generate_orders_dataset` | `ml/dataset.py` |
| 14 | `validate_dataset` | `ml/dataset.py` (règles en table) |
| 18 | `clean_orders_data` | `ml/dataset.py` |
| 20 | `FEATURE_COLUMNS`, `NUMERIC_FEATURES`… | `domain/features.py` |
| 22-29 | Split, pipeline, entraînement, métriques | `ml/training.py` |
| 33-35 | `predict_order_eligibility`, seuil | `services/prediction_service.py` + `POST /v1/predictions` |
| 40 | Tests fonctionnels de prédiction | `tests/test_prediction_service.py`, `tests/test_api.py` |
| 42-44 | Sauvegarde / rechargement joblib | `infrastructure/filesystem/model_repository.py` |
| — | Collecte des commandes | `services/order_service.py` + `POST/GET /v1/orders` |
| 46, 51 | Batch | Séance 5 |
| 48 | Flux temps réel | Séance 5-6 |
| 55 | Model card | Séance 3 (`GET /v1/model`) |
| 12, 31, 54 | Graphiques exploratoires | Non repris (expérimentation, YAGNI) |

## Principes SOLID appliqués

- **S — Responsabilité unique** : une classe = une raison de changer (`SqliteOrderStore` ne fait que persister, `PredictionService` ne fait que prédire, les routes ne font que traduire HTTP ↔ service).
- **O — Ouvert/fermé** : ajouter PostgreSQL, MLflow ou S3 = ajouter une classe dans `infrastructure/`, sans modifier services ni routes.
- **L — Substitution de Liskov** : la même suite `tests/test_order_store.py` tourne sur `InMemoryOrderStore` et `SqliteOrderStore`.
- **I — Ségrégation des interfaces** : deux ports courts et séparés (commandes / modèle) plutôt qu'un « repository » fourre-tout.
- **D — Inversion des dépendances** : services et API dépendent des ABC ; seul `api/app.py` (composition root) instancie les classes concrètes.
- **DRY** : la liste des variables n'existe qu'une fois (`domain/features.py`) ; **YAGNI** : pas de batch, model card ni MLflow avant leur séance.

## Éléments à industrialiser (tableau de la cellule 63)

| Élément | Séance | Solution technique retenue |
|---|---|---|
| Collecte de données | 1 | `POST /v1/orders` → `OrderService` → `SqliteOrderStore` ([ADR-0001](adr/ADR-0001-stockage-commandes-clients.md)) |
| Exposition d'une fonction de prédiction | 1 | FastAPI `POST /v1/predictions`, contrat OpenAPI vérifié par les tests |
| Entraînement du modèle | 1 | `scripts/train.py` (séparé du service) |
| Prédiction à l'aide du modèle | 1 | `PredictionService` + modèle chargé au démarrage via `FileModelRepository` ([ADR-0002](adr/ADR-0002-stockage-artefacts-modele.md)) |
| Environnement (dev → test → prod) | 1 & 3 | Configuration par variables d'environnement (`APP_ENV`, `MODEL_VERSION`, `DATABASE_PATH`, `MODELS_DIR`, `PREDICTION_THRESHOLD`) |

## Lancer l'application

```bash
pip install -e ".[dev]"
python scripts/train.py --version 1.0.0     # publie artifacts/models/1.0.0
uvicorn express_delivery.main:app --reload  # http://localhost:8000/docs
pytest                                      # 34 tests
```

Related: [ADR-0001](adr/ADR-0001-stockage-commandes-clients.md) · [ADR-0002](adr/ADR-0002-stockage-artefacts-modele.md) · [Journal séance 1](journal/2026-10-06-seance-1.md)
