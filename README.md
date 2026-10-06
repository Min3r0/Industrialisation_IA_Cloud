---
title: API éligibilité livraison express
date: 2026-10-06
tags: [readme, fastapi]
---

# API éligibilité livraison express

Industrialisation du notebook `project_test_v1_final_final2.ipynb` (M2 EIA, cours « Industrialisation de l'IA dans le cloud »).

## Démarrage

```bash
python -m venv .venv && .venv\Scripts\activate        # Windows (Linux/macOS : source .venv/bin/activate)
pip install -e ".[dev]"
python scripts/train.py --version 1.0.0                # publie artifacts/models/1.0.0
uvicorn express_delivery.main:app --reload             # http://localhost:8000/docs
pytest
```

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `APP_ENV` | `dev` | Environnement courant |
| `MODELS_DIR` | `artifacts/models` | Dépôt des versions de modèle (ADR-0002) |
| `MODEL_VERSION` | `1.0.0` | Version de modèle servie |
| `DATABASE_PATH` | `data/orders.db` | Fichier SQLite des commandes (ADR-0001) |
| `PREDICTION_THRESHOLD` | `0.5` | Seuil de décision |

Documentation : [Architecture](docs/architecture.md) · [ADR-0001](docs/adr/ADR-0001-stockage-commandes-clients.md) · [ADR-0002](docs/adr/ADR-0002-stockage-artefacts-modele.md) · [Journal séance 1](docs/journal/2026-10-06-seance-1.md)
