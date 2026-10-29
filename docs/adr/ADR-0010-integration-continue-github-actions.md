---
title: ADR-0010 — Intégration continue et publication de l'image (GitHub Actions)
date: 2026-10-29
tags: [adr, ci, cd, github-actions, pytest, pylint, docker, securite, seance-4]
aliases: [ADR-0010, CI, GitHub Actions, Intégration continue, Publication image]
status: Accepté
---

# ADR-0010 — Intégration continue et publication de l'image (GitHub Actions)

**Status :** Accepté
**Date :** 29/10/2026

## Contexte

- Le dépôt suit Gitflow ([ADR-0008](ADR-0008-workflow-git-gitflow.md)) : chaque changement passe par une pull request vers `develop` ou `main`, mais rien ne vérifie automatiquement qu'il ne casse rien. L'ADR-0008 prévoyait « une future CI (`pytest` sur chaque pull request) ».
- L'image Docker ([ADR-0009](ADR-0009-conteneurisation-image-docker.md)) est construite à la main. L'ADR-0009 renvoyait à la CI : étiquettes OCI, épinglage, Trivy, hadolint, compression zstd, SBOM, publication.
- Le cours demande : tester l'application (pytest + pylint) et automatiser la création d'une image Docker lors d'une release.
- Le dépôt est sur GitHub (`Min3r0/Industrialisation_IA_Cloud`).

## Options considérées

| Sujet | Options | Retenu |
|---|---|---|
| Moteur de CI | **GitHub Actions** · Azure Pipelines · GitLab CI | GitHub Actions : intégré au dépôt, gratuit pour un dépôt public, jeton `GITHUB_TOKEN` fourni, statuts visibles dans les pull requests |
| Analyse statique | **pylint** · ruff · flake8 | pylint, demandé par le cours ; configuration dans `pyproject.toml` |
| Gate pylint | 10/10 obligatoire · **note minimale + aucune alerte** | `fail-under = 9.0` et `fail-on = E, W, F` : toute erreur ou alerte bloque ; les conventions (docstrings manquantes) baissent la note sans bloquer tant qu'elle reste ≥ 9 |
| Déclencheur de publication | push sur `main` · push d'un tag `v*` · **release GitHub publiée** | Release publiée : acte volontaire, porte des notes de version, rejouable ; correspond à la fin de la procédure Gitflow |
| Registre | Azure Container Registry · Docker Hub · **GitHub Container Registry (ghcr.io)** | ghcr.io : aucun secret à créer (`GITHUB_TOKEN`), image liée au dépôt. ACR reste la cible de déploiement (ADR-0003) : voir Conséquences |
| Épinglage des actions | tag (`@v7`) · **empreinte de commit** | Empreinte SHA + commentaire de version : un tag peut être déplacé par un attaquant (attaques de chaîne d'approvisionnement sur des actions populaires), une empreinte non. Mises à jour par Dependabot |

## Décision

### 1. Workflow `ci.yml` — à chaque pull request et push sur `main` / `develop`

| Job | Contenu | Échoue si |
|---|---|---|
| `lint` | `pylint src scripts` (règles du projet) puis `pylint tests` (docstrings et `redefined-outer-name` désactivés : fixtures pytest) | note < 9,0 ou au moins un message E / W / F |
| `test` | `pytest -ra --junitxml` (68 tests, données synthétiques, aucun secret) ; rapport JUnit en artefact | un test échoue |
| `docker` | hadolint, puis `docker build --target test` : pytest dans l'image élaguée | avertissement hadolint ou test KO dans l'image |

- Les trois jobs tournent en parallèle ; une étape partagée (action composite `.github/actions/setup-python-env`) installe Python 3.13 et les **mêmes fichiers verrouillés avec empreintes** que l'image (`requirements/test.lock`, plus `requirements/lint.lock` pour pylint) : pas de duplication (DRY), environnement identique en local, en CI et dans l'image.
- `permissions: contents: read`, `persist-credentials: false` : la CI ne peut rien modifier.
- Un nouveau push sur une pull request annule l'exécution précédente (`concurrency`).

### 2. Workflow `release.yml` — à la publication d'une release GitHub

1. **`quality`** : rappelle `ci.yml` (`workflow_call`) sur le commit tagué ; rien n'est publié si la CI échoue.
2. **Garde-fous** : tag au format `vX.Y.Z` ; tag = version de `pyproject.toml` = `__version__` ; commit tagué présent sur `main` (Gitflow).
3. **Image candidate** (`target: runtime`, chargée localement) avec les étiquettes OCI (`version`, `revision`, `created`).
4. **Test de démarrage** avec la configuration par défaut (`APP_ENV=prod`) et les durcissements de Compose (`--read-only`, `--cap-drop ALL`, `no-new-privileges`) : `/health` = 200 et bonne version, `/health/ready` = 503 sans modèle, `/docs` = 404, pas d'en-tête `server`, UID 10001, pas de pip.
5. **Trivy** : vulnérabilités HIGH/CRITICAL corrigeables et secrets → publication bloquée.
6. **Publication** sur `ghcr.io/min3r0/industrialisation_ia_cloud` : tags `X.Y.Z`, `X.Y`, `X`, `latest` (versions stables), compression **zstd niveau 3**, **SBOM** et **attestation de provenance** (SLSA, `mode=max`) ; l'empreinte publiée est affichée dans le résumé du run (déploiement par empreinte, ADR-0004).

Le cache de construction (`type=gha`) est partagé entre les deux workflows : la publication réutilise les couches déjà construites par la CI.

### 3. Sécurité de la chaîne CI/CD

| Mesure | Effet |
|---|---|
| Actions tierces épinglées par empreinte de commit | un tag déplacé ne change pas le code exécuté |
| Dependabot (`github-actions`, mensuel, vers `develop`) | les empreintes restent à jour, chaque mise à jour passe par une pull request |
| Permissions minimales par job (`packages: write` seulement pour la publication) | un job compromis ne peut pas pousser d'image ni modifier le dépôt |
| Aucun secret personnel : `GITHUB_TOKEN` éphémère | rien à faire tourner ni à fuiter |
| Dépendances installées avec `--require-hashes --only-binary=:all:` | même protection qu'à la construction de l'image (ADR-0009) |

## Conséquences

- Les checks `Analyse statique (pylint)`, `Tests (pytest)` et `Image Docker (…)` deviennent des **conditions de fusion** dans les règles de protection de `main` et `develop` (à cocher dans GitHub, voir [guide CI](../ci.md)).
- Publier une version = fusionner `release/X.Y.Z` dans `main`, taguer, **créer la release GitHub** ; l'image suit automatiquement. Oublier de mettre à jour `pyproject.toml` **et** `__init__.py` fait échouer la publication (voulu).
- Le paquet ghcr.io est privé à sa création : le rendre public ou donner l'accès à Azure Container Apps (voir guide).
- Pylint : il ne reste que des docstrings manquantes dans `src/` et `scripts/` (31 fonctions, 29 classes, 3 modules ; note 9,22). Le seuil `fail-under` sera relevé à mesure qu'elles sont ajoutées, jusqu'à 10.
- Quatre imports volontairement locaux (MLflow, ADR-0007) sont marqués `# pylint: disable=import-outside-toplevel` avec leur justification.
- Pistes : pousser aussi vers Azure Container Registry (connexion OIDC `azure/login`, sans secret longue durée) puis déployer la révision « green » (ADR-0004) ; signer l'image (cosign) ; couverture de tests (`pytest-cov`) ; épingler l'image de base par empreinte via Dependabot `docker`.

Related: [ADR-0004](ADR-0004-strategie-deploiement-blue-green.md) · [ADR-0007](ADR-0007-suivi-experiences-mlflow.md) · [ADR-0008](ADR-0008-workflow-git-gitflow.md) · [ADR-0009](ADR-0009-conteneurisation-image-docker.md) · [Guide CI](../ci.md) · [Journal CI](../journal/2026-10-29-github-actions.md)
