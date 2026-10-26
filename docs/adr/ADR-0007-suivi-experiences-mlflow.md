---
title: ADR-0007 — Suivi des entraînements avec MLflow et découpage du code ML
date: 2026-10-26
tags: [adr, architecture, mlops, mlflow, solid, entrainement]
aliases: [ADR-0007, ExperimentTracker, MLflow tracking]
status: Accepté
---

# ADR-0007 — Suivi des entraînements avec MLflow et découpage du code ML

**Status :** Accepté
**Date :** 26/10/2026
**Complète :** [ADR-0002 — Stockage des artefacts du modèle](ADR-0002-stockage-artefacts-modele.md) (sans la remplacer)

## Contexte

- Le notebook suivait déjà ses expériences avec MLflow (`mlflow.db`, `mlruns/`) ; notre `scripts/train.py` ne gardait que le dernier `manifest.json` : impossible de comparer deux entraînements ni de retrouver les paramètres d'un modèle publié.
- La correction de l'intervenant (`correction/livraison_express_lite`, voir [Comparaison avec la correction](../journal/2026-10-26-comparaison-correction.md)) trace chaque entraînement dans MLflow et découpe le code ML en petites classes (`MLPipeline`, `TrainTestSplitter`, `MLTrainer`, `MLPredict`).
- Notre `ml/training.py` mélangeait dans une seule fonction : construction de la pipeline, découpage, entraînement et calcul des métriques.
- L'ADR-0002 prévoyait MLflow comme évolution (option C, Model Registry).

## Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Pas de suivi (existant) | Rien à installer | Aucun historique des entraînements |
| B. **MLflow Tracking** à l'entraînement, l'API charge toujours `artifacts/models/X.Y.Z` | Historique, comparaison des runs, modèle re-chargeable depuis MLflow ; l'API ne dépend pas d'un serveur MLflow | Deux endroits contiennent le modèle (MLflow + dépôt local) |
| C. MLflow Tracking + **Model Registry** comme source du modèle servi | Une seule source, stades Staging/Production | L'API doit joindre MLflow au démarrage ; remet en cause l'ADR-0002 avant d'en avoir besoin |

## Décision

**Option B.** L'ADR-0002 reste en vigueur pour le modèle **servi** ; MLflow sert à l'**historique** des entraînements.

1. **Port `ExperimentTracker`** (`abstractions/experiment_tracker.py`) avec un seul objet échangé, `TrainingRun` (nom, paramètres, métriques, modèle, exemple d'entrée, tags).
   - `infrastructure/tracking/mlflow_tracker.py` : `MlflowExperimentTracker` — un run par entraînement : `log_params`, `log_metrics`, tags, `mlflow.sklearn.log_model` (signature déduite de 5 lignes d'entrée, format skops).
   - `infrastructure/tracking/null_tracker.py` : `NullExperimentTracker` pour `--no-tracking`.
2. **Découpage du code ML en classes à responsabilité unique** (inspiré de la correction) :

   | Classe | Fichier | Seule responsabilité | Cellules |
   |---|---|---|---|
   | `PipelineFactory` | `ml/pipeline_factory.py` | Décrire prétraitement + classifieur | 22-24 |
   | `TrainTestSplitter` | `ml/splitter.py` | Séparer X / y puis train / test stratifié | 22 |
   | `ModelEvaluator` | `ml/evaluator.py` | Calculer les 5 métriques | 27-29 |
   | `ModelTrainer` | `ml/trainer.py` | Enchaîner les trois précédents + le tracker | 25-29 |
   | `build_feature_frame` | `ml/feature_frame.py` | Commandes → DataFrame (entraînement **et** prédiction) | 34 |

   `ModelTrainer` reçoit ses quatre collaborateurs au constructeur : aucun `Settings()` caché, aucun singleton (défauts relevés dans la correction).
3. **Lien entre les deux mondes** : le `run_id` MLflow est écrit dans `manifest.json` (`mlflow_run_id`) ; depuis un modèle servi, on retrouve son run.
4. `scripts/train.py` devient la **composition root de l'entraînement** (choix des implémentations), et vérifie `ModelRepository.exists(version)` **avant** d'entraîner pour ne pas créer de run orphelin.
5. Configuration : `MLFLOW_TRACKING_URI` (défaut `sqlite:///mlflow.db`), `MLFLOW_EXPERIMENT_NAME` (défaut `livraison-express`), `RANDOM_SEED` (défaut 42).
6. MLflow est une dépendance **d'entraînement** (`pip install -e ".[train]"`), importée seulement à la construction de `MlflowExperimentTracker` : l'API n'en a pas besoin.

## Conséquences

- Chaque `python scripts/train.py --version X.Y.Z` laisse un run consultable avec `mlflow ui --backend-store-uri sqlite:///mlflow.db`.
- Les métriques sont identiques à l'ancien code et à la correction (accuracy 0,768, ROC AUC 0,849 avec scikit-learn 1.9.1) : le découpage n'a pas changé le modèle.
- Le dossier `mlruns/` (artefacts MLflow) et `mlflow.db` grossissent à chaque run : ne pas les embarquer dans l'image de l'API.
- Ajouter un autre outil de suivi (Weights & Biases, Azure ML) = une nouvelle classe `ExperimentTracker`, sans modifier `ModelTrainer` (O de SOLID).
- Les manifestes antérieurs (sans `mlflow_run_id`) restent lisibles.
- Passage au Model Registry (option C) : nouvelle ADR qui remplacera l'ADR-0002 le jour où l'API tournera sur plusieurs instances.

Related: [ADR-0002](ADR-0002-stockage-artefacts-modele.md) · [Architecture](../architecture.md) · [Journal du 26/10](../journal/2026-10-26-mlflow-decoupage-ml.md)
