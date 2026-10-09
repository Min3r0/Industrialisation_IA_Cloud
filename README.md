---
title: API éligibilité livraison express
date: 2026-10-06
tags: [readme, fastapi, securite]
---

# API éligibilité livraison express

Industrialisation du notebook `project_test_v1_final_final2.ipynb` (M2 EIA, cours « Industrialisation de l'IA dans le cloud »).

## Démarrage

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/train.py --version 1.0.0     # publie artifacts/models/1.0.0
pytest
uvicorn express_delivery.main:app --reload  # http://localhost:8000/docs
```

**Linux / macOS (bash)**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/train.py --version 1.0.0     # publie artifacts/models/1.0.0
pytest
uvicorn express_delivery.main:app --reload  # http://localhost:8000/docs
```

La racine `/` renvoie 404 (aucune route dans le contrat) : l'interface de test est `/docs`.

## Clés d'API (ADR-0006)

En dev l'authentification est désactivée. Pour la tester localement, en trois étapes.

1. Générer une clé (`--id` est seulement le nom du client à qui elle est destinée) :

   ```bash
   python scripts/create_api_key.py --id front --role user --days 30
   ```

   Le script affiche la **clé** (`sk_dev_…`, à donner au client) et l'**entrée** `front:<empreinte>:user:<date>` à mettre dans `API_KEYS`.

2. Définir les variables d'environnement **dans le terminal qui lancera uvicorn**, en remplaçant l'exemple par l'entrée affichée :

   **Windows (PowerShell)** — `set` ne fonctionne pas ici, il faut `$env:` :

   ```powershell
   $env:AUTH_ENABLED = "true"
   $env:API_KEYS = "front:<empreinte>:user:<date>"
   uvicorn express_delivery.main:app
   ```

   **Linux / macOS (bash)** :

   ```bash
   export AUTH_ENABLED=true
   export API_KEYS="front:<empreinte>:user:<date>"
   uvicorn express_delivery.main:app
   ```

   Au démarrage, le message `Authentification désactivée` ne doit **pas** apparaître. Les variables ne valent que pour ce terminal.

3. Appeler ensuite les routes `/v1/*` avec l'en-tête `X-API-Key: <clé>` (bouton *Authorize* de `/docs`). Réponses : 401 clé absente/invalide/expirée, 403 rôle insuffisant, 429 trop de requêtes (en-tête `Retry-After`).

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `APP_ENV` | `dev` | Environnement courant |
| `MODELS_DIR` | `artifacts/models` | Dépôt des versions de modèle (ADR-0002) |
| `MODEL_VERSION` | `1.0.0` | Version de modèle servie |
| `DATABASE_PATH` | `data/orders.db` | Fichier SQLite des commandes (ADR-0001) |
| `PREDICTION_THRESHOLD` | `0.5` | Seuil de décision |
| `AUTH_ENABLED` | `false` (`true` si `APP_ENV=prod`, obligatoire) | Exige une clé d'API sur `/v1/*` (ADR-0006) |
| `API_KEYS` | vide | Empreintes des clés `id:sha256:rôle:AAAA-MM-JJ;…` — secret Key Vault en prod |
| `RATE_LIMIT_PER_MINUTE` | `60` | Requêtes par minute et par clé, par instance (ADR-0005) |
| `EXPOSE_DOCS` | `true` (`false` si `APP_ENV=prod`) | Expose `/docs`, `/redoc`, `/openapi.json` |

Documentation : [Architecture](docs/architecture.md) · [ADR-0001](docs/adr/ADR-0001-stockage-commandes-clients.md) · [ADR-0002](docs/adr/ADR-0002-stockage-artefacts-modele.md) · [ADR-0003 Hébergement](docs/adr/ADR-0003-hebergement-plateforme-deploiement.md) · [ADR-0004 Blue/Green](docs/adr/ADR-0004-strategie-deploiement-blue-green.md) · [ADR-0005 Entrées/sorties](docs/adr/ADR-0005-securite-entrees-sorties.md) · [ADR-0006 Accès à la donnée](docs/adr/ADR-0006-securite-acces-donnee.md)
