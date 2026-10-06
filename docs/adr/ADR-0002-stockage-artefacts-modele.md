---
title: ADR-0002 — Où stocker les artefacts du modèle de Machine Learning
date: 2026-10-06
tags: [adr, architecture, stockage, modele, mlops, seance-1]
aliases: [ADR-0002, ModelRepository, Stockage des artefacts]
status: Accepté
---

# ADR-0002 — Où stocker les artefacts du modèle de Machine Learning

**Status :** Accepté
**Date :** 06/10/2026
**Séance :** 1

## Contexte

L'API doit **charger un modèle déjà entraîné au démarrage**, sans réentraîner à chaque redéploiement (cellule 43 du notebook). Elle doit aussi connaître la version du modèle servi (champ `model_version` de chaque prédiction, sonde `/health/ready`, puis model card `GET /v1/model` en séance 3).

Caractéristiques du besoin :

- Un artefact = la pipeline scikit-learn (préprocesseur + régression logistique) sérialisée avec joblib, **≈ 5 Ko**, + ses métadonnées (variables, métriques, date d'entraînement).
- Écrit **rarement** (à chaque entraînement), lu **à chaque démarrage** de l'API.
- Le notebook écrivait tout à plat dans `artifacts/` (`express_delivery_model.joblib`, `features.json`, `metrics.json`) : un nouvel entraînement **écrase** l'ancien modèle, impossible de revenir en arrière.
- joblib repose sur `pickle` : charger un fichier modifié par un tiers peut **exécuter du code arbitraire**.
- MLflow est déjà utilisé dans le notebook pour le suivi des expériences (`mlflow.db`, `mlruns/`) ; il est au programme de la séance 4.

## Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Répertoire local à plat (notebook) | Déjà en place, aucun service | Écrasement à chaque entraînement, pas de versionnage, pas de retour arrière |
| B. **Répertoire local versionné** `artifacts/models/<version>/` | Aucun service, versions immuables, retour arrière = changer une variable d'environnement | Pas partagé entre machines ; registre « fait main » |
| C. MLflow Model Registry | Versionnage natif, stades (Staging/Production), lien avec les runs d'entraînement | Service supplémentaire à faire tourner et à joindre au démarrage de l'API ; prévu en séance 4 |
| D. Stockage objet (S3, Azure Blob, GCS) | Partagé, durable, adapté au cloud et au multi-instances | Compte cloud, gestion des identifiants et des droits ; prématuré en séance 1 |

## Décision

**Option B — répertoire local versionné**, derrière l'abstraction `ModelRepository` (ABC).

Disposition sur disque :

```text
artifacts/models/
└── 1.0.0/
    ├── model.joblib      # pipeline scikit-learn
    └── manifest.json     # version, type, cible, variables, métriques, date, version de scikit-learn, sha256
```

- `src/express_delivery/abstractions/model_repository.py` : le port `ModelRepository` (`load(version)`, `save(estimator, metadata)`).
- `src/express_delivery/infrastructure/filesystem/model_repository.py` : `FileModelRepository`.
- `scripts/train.py` entraîne et **publie** une version ; l'API la **charge**. L'entraînement et le service sont séparés.
- La version servie est **explicite** : variable d'environnement `MODEL_VERSION` (défaut `1.0.0`), au format `X.Y.Z` (un format invalide est refusé, ce qui bloque aussi les chemins du type `../`).
- Une version publiée est **immuable** : `save` refuse d'écraser un dossier existant.
- L'empreinte **SHA-256** de `model.joblib` est écrite dans le manifeste et **vérifiée avant chaque chargement** ; un écart refuse le modèle.
- Si le modèle est absent ou corrompu, l'API démarre quand même : `/health` répond 200, `/health/ready` répond 503 et `/v1/predictions` répond 503 `model_unavailable`.

Pourquoi : l'option B corrige les deux défauts réels de l'option A (écrasement, absence de version) sans ajouter de service (YAGNI). L'abstraction `ModelRepository` permet de passer à MLflow ou à un stockage objet en ajoutant une classe (`MlflowModelRepository`, `S3ModelRepository`) sans modifier les services ni l'API.

Évolution probable vers l'**option C (MLflow Model Registry)** en séance 4, puis **D** (stockage objet) dès que l'API tourne sur plusieurs machines dans le cloud.

## Conséquences

- Chaque version du modèle est identifiée explicitement ; déployer un nouveau modèle = publier `X.Y.Z` puis changer `MODEL_VERSION` ; revenir en arrière = remettre l'ancienne valeur.
- Les dossiers `artifacts/models/*` doivent être fournis à l'API au déploiement (copie, volume Docker…) : ils ne sont pas regénérés au démarrage.
- La version de scikit-learn utilisée à l'entraînement est notée dans le manifeste ; un écart au chargement produit un avertissement dans les logs (risque d'incompatibilité de désérialisation). Il faut figer les versions des dépendances.
- La vérification SHA-256 protège contre une corruption ou une modification accidentelle, **pas** contre un attaquant qui pourrait réécrire à la fois le modèle et le manifeste : en prod, le dossier doit être en lecture seule pour l'API.
- Les anciens fichiers à plat de `artifacts/` produits par le notebook restent en place mais ne sont plus lus par l'API.
- Le jour où MLflow Registry est adopté (séance 4), cette ADR devra être marquée « Status : Superseded by ADR-000X » + nouvelle décision écrite.

Related: [ADR-0001 — Stockage des commandes](ADR-0001-stockage-commandes-clients.md) · [Architecture de l'application](../architecture.md)
