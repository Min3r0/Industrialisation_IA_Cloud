---
title: ADR-0013 — Orchestration du réentraînement périodique
date: 2026-11-20
tags: [adr, architecture, ml, orchestration, reentrainement, seance-5]
aliases: [ADR-0013, Orchestrateur, Réentraînement planifié, Orchestration entraînement]
status: Accepté
---

# ADR-0013 — Orchestration du réentraînement périodique

**Status :** Accepté
**Date :** 20/11/2026
**Séance :** 5, point *j* de la checklist (« un orchestrateur pour entraîner le modèle »)
Suite de : [ADR-0012](ADR-0012-cible-express-regle-metier-erp.md) · [ADR-0011](ADR-0011-source-donnees-postgresql-mongodb.md)

## Contexte

Le cours #4 (« Orchestration de l'entraînement ») pose deux principes :

- l'entraînement est un **processus d'exécution**, pas de construction d'application : il ne relève pas de la CI/CD ;
- on réentraîne **dès qu'il y a assez de nouvelles données**, à une fréquence fixée par le projet. L'orchestrateur est l'élément qui déclenche ce processus (le cours cite Airflow comme exemple).

Le cours #5 précise le problème : un traitement toutes les 2 minutes perd en fraîcheur, un traitement toutes les nuits introduit de la latence, et le traitement par lot impose sa chronologie.

Aujourd'hui, `scripts/train.py --source erp` entraîne à la demande. Il manque un déclenchement automatique, qui décide seul s'il faut entraîner, sans republier une version déjà existante.

## Décision

1. **Un pipeline à trois étapes nommées** (`ml/retraining.py`) : lecture des commandes récentes → contrôle de fraîcheur → publication d'une version.
2. **Fraîcheur** : on n'entraîne que si la fenêtre (30 jours par défaut) contient au moins 500 commandes valides. Sinon l'exécution est *sautée* et le motif est journalisé. Les commandes plus anciennes ne comptent pas.
3. **Reprise** : une erreur de lecture (`OrderSourceError`) déclenche jusqu'à 3 tentatives, avec une pause croissante (60 s, puis 120 s). Après la dernière tentative, l'erreur remonte et le code de sortie est 1.
4. **Idempotence** : la version est `erp-AAAAMMJJ`. Si elle existe déjà, rien n'est lu ni entraîné. Une seule publication par jour, même si la planification se déclenche plusieurs fois.
5. **Planification** : `scripts/retrain.py` s'exécute une fois, ou en boucle avec `--every-hours N`. La boucle ne s'arrête pas sur une erreur ponctuelle. En production, la planification sera confiée à l'orchestrateur choisi (voir alternatives).
6. **Injection** : le pipeline reçoit la source, la fonction de publication, la vérification d'existence, la règle et une horloge (`Clock`). Il ne connaît ni MongoDB ni scikit-learn : il se teste sans base ni modèle.
7. **Pas de nouvelle dépendance** : l'orchestrateur est écrit en Python standard, comme le reste du projet. Le `requirements/test.lock` (installé avec `--require-hashes`) ne change pas.

### Règles par défaut (hypothèses d'exploitation)

| Règle | Valeur | Option |
|---|---|---|
| Fenêtre de fraîcheur | 30 jours | `--window-days` |
| Commandes minimum dans la fenêtre | 500 | `--min-orders` |
| Tentatives de lecture | 3, pause de 60 s × n° de tentative | `RetrainingPolicy` |
| Période | à la demande, ou toutes les N heures | `--every-hours` |

## Alternatives écartées

| Option | Pourquoi pas maintenant |
|---|---|
| **Airflow** (exemple du cours) | Il faut un scheduler, une base de métadonnées, un webserver et un conteneur dédié : trop lourd pour un pipeline d'une seule tâche, et impossible à vérifier ici (pas de Docker). **C'est la voie d'évolution** si le projet ajoute des étapes (ETL, évaluation, déploiement). |
| **Prefect / Dagster** | Plus légers qu'Airflow, mais ajoutent une dépendance à verrouiller avec hashes (`test.lock`) et un serveur à exploiter. |
| **GitHub Actions planifié** (`schedule:`) | Le cours distingue explicitement entraînement et CI/CD. Et l'entraînement a besoin du réseau de l'entreprise (MongoDB), inaccessible depuis GitHub. |
| **Tâche planifiée Windows / cron** seule | Possible en local, mais aucune reprise ni journal structuré. Reste une option pour la démonstration. |

## Conséquences

- **Vérifié :** 10 tests unitaires (`tests/test_retraining.py`) : publication, seuil, fenêtre, idempotence, reprises, abandon, validation des règles. Le script échoue proprement sans `MONGO_URI` et sur serveur injoignable (code 1).
- **Non vérifié :** une exécution complète sur la vraie base MongoDB (Docker non disponible dans mon environnement).
- Les commandes de l'ERP arrivent avec des dates futures dans le simulateur (flux « live »). Elles sont **exclues** de la fenêtre : la fraîcheur se mesure donc sur les dates passées ou du jour.
- Un réentraînement publie une version `erp-AAAAMMJJ` : l'API ne la charge que si `MODEL_VERSION` la désigne (ADR-0002). La promotion automatique n'est **pas** faite : c'est un choix de mise en production à valider.
- La règle d'éligibilité (ADR-0012) reste une hypothèse : le réentraînement répète la règle, il ne l'améliore pas.

## Critères de réexamen

- Plus de trois étapes, ou une étape qui doit tourner sur un autre serveur : passer à **Airflow** (le pipeline reste une classe testable, il devient une tâche).
- Les livraisons réalisées deviennent disponibles : remplacer la règle, garder le pipeline.
- Besoin de promotion automatique après évaluation : nouvelle ADR (seuils de métriques, registre de modèles).

Related: [ADR-0012](ADR-0012-cible-express-regle-metier-erp.md) · [ADR-0011](ADR-0011-source-donnees-postgresql-mongodb.md) · [ADR-0007](ADR-0007-suivi-experiences-mlflow.md) · [ADR-0002](ADR-0002-stockage-artefacts-modele.md) · [Architecture](../architecture.md) · [Journal](../journal/2026-11-20-orchestration-reentrainement.md) · [Index](../../INDEX.md)
