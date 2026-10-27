---
title: ADR-0009 — Conteneuriser l'API (image Docker)
date: 2026-10-26
tags: [adr, architecture, docker, conteneur, securite, optimisation, seance-3]
aliases: [ADR-0009, Image Docker, Conteneurisation, Dockerfile]
status: Accepté
---

# ADR-0009 — Conteneuriser l'API (image Docker)

**Status :** Accepté
**Date :** 26/10/2026
**Séance :** 3

## Contexte

L'[ADR-0003](ADR-0003-hebergement-plateforme-deploiement.md) fait de l'**image de conteneur** le livrable de déploiement (Azure Container Apps, registre privé Azure Container Registry). Elle impose deux règles : l'image ne contient **ni secret ni modèle** (le modèle vient d'Azure Files, monté en lecture seule sur `MODELS_DIR`). La [séance 2](../journal/2026-10-09-seance-2.md) a listé les attentes : construction en plusieurs étapes, utilisateur non root, `HEALTHCHECK`.

Contraintes :

- dépendances scientifiques lourdes (numpy, pandas, scipy, scikit-learn : environ 200 Mo installés) ;
- le modèle publié a été entraîné avec **scikit-learn 1.9.1** (`manifest.json`) : l'image doit utiliser la même version, sinon le chargement par joblib/pickle peut échouer ou changer les résultats ;
- Blue/Green ([ADR-0004](ADR-0004-strategie-deploiement-blue-green.md)) : arrêt propre sur `SIGTERM`, démarrage rapide, image identique d'un environnement à l'autre (seules les variables changent) ;
- sécurité ([ADR-0005](ADR-0005-securite-entrees-sorties.md), [ADR-0006](ADR-0006-securite-acces-donnee.md)) : aucune fuite d'information technique, authentification obligatoire en production.

## Options considérées

| Sujet | Options | Retenu |
|---|---|---|
| Image de base | `python:3.13` complète (~1 Go) · `python:3.13-slim` (Debian) · `python:3.13-alpine` · distroless | **`python:3.13-slim-trixie`** : roues `manylinux` compatibles (Alpine = musl, recompilation de numpy/scipy), outils de diagnostic minimaux. Distroless écarté : pas de Python 3.13 officiel stable au moment du choix et débogage plus difficile |
| Construction | une étape · **plusieurs étapes** | `builder` → `test` (facultative) → `runtime` |
| Dépendances | `requirements.txt` à bornes ouvertes · **fichier verrouillé avec empreintes** | `requirements/prod.lock` généré par `uv pip compile --generate-hashes`, installé avec `--require-hashes --only-binary=:all:` |
| Modèle | copié dans l'image · **monté au démarrage** | Volume en lecture seule sur `/models` (ADR-0002, ADR-0003) |
| Serveur | gunicorn + workers uvicorn · **uvicorn seul, 1 processus** | La montée en charge se fait par répliques Container Apps, pas par workers (YAGNI) ; le limiteur de débit reste cohérent par processus |
| Fichier `.dockerignore` | liste noire · **liste blanche** | Tout est exclu sauf `pyproject.toml`, `requirements/`, `src/`, `tests/`, `openapi.yml` |

## Décision

### 1. Structure du `Dockerfile`

| Étape | Rôle | Contenu final |
|---|---|---|
| `builder` | crée `/opt/venv` **sans pip**, y installe les dépendances verrouillées (couche mise en cache) puis le paquet `express-delivery` (couche qui change souvent) ; supprime les dossiers `tests/` des bibliothèques, sources Cython, en-têtes C, `.pyi` | jeté |
| `test` | `builder` + `requirements/test.lock` (pytest, httpx, MLflow…) ; lance `pytest` **sur les dépendances réellement embarquées** | jeté (cible `--target test`, pour la CI) |
| `runtime` | image de base propre + `/opt/venv` copié ; pip désinstallé ; utilisateur `app` (UID/GID 10001) | **image livrée** |

### 2. Optimisation

- **Ordre des couches** : le fichier verrouillé est copié avant le code ; modifier `src/` ne réinstalle pas les dépendances.
- **Cache BuildKit** (`--mount=type=cache,target=/root/.cache/pip`) : les roues ne sont pas retéléchargées et ne finissent pas dans l'image.
- **Aucun outil de build dans l'image finale** (ni pip, ni setuptools, ni compilateur, ni dépendances de dev, ni MLflow : ADR-0007).
- **Élagage** des suites de tests embarquées par numpy, pandas, scipy et scikit-learn ; les 68 tests du projet passent dans l'image élaguée (étape `test`).
- **Compression des couches** : gzip par défaut ; **zstd niveau 3** recommandé à la publication (mesures dans le [guide Docker](../docker.md#compression)).

### 3. Sécurisation

| Mesure | Où | Effet |
|---|---|---|
| Utilisateur non root `10001:10001`, sans shell ni home | `Dockerfile` | une faille dans l'API ne donne pas root dans le conteneur |
| Code et venv appartenant à `root`, non modifiables | `COPY --chown=root:root` | le processus ne peut pas altérer son propre code |
| Pas de pip dans l'image | `Dockerfile` | impossible d'installer un paquet depuis le conteneur |
| Dépendances avec empreintes SHA-256, roues uniquement | `--require-hashes --only-binary=:all:` | protection contre un paquet altéré ou un `setup.py` malveillant |
| `APP_ENV=prod` par défaut | `ENV` | authentification obligatoire, `/docs` masqué si rien n'est configuré (sécurité par défaut) |
| En-tête `server: uvicorn` supprimé | `--no-server-header` | ne divulgue pas la technologie (ADR-0005) |
| Contexte de build en liste blanche | `.dockerignore` | `.env`, `mlflow.db`, `data/`, `.git`, `correction/` ne peuvent pas entrer dans l'image |
| Système de fichiers racine en lecture seule, `/tmp` en `noexec` | `docker-compose.yml` (`read_only`, `tmpfs`) | rien ne peut être écrit hors de `/data` |
| Aucune capacité Linux, pas d'élévation de privilèges | `cap_drop: [ALL]`, `no-new-privileges` | limite l'impact d'une évasion |
| Limites de ressources | `mem_limit`, `cpus`, `pids_limit` | une fuite mémoire ou une *fork bomb* ne fait pas tomber l'hôte |
| Port publié sur `127.0.0.1` seulement | `docker-compose.yml` | l'API locale n'est pas exposée au réseau |
| Image de base épinglée par empreinte, scan Trivy, lint hadolint | CI ([guide](../docker.md)) | image reproductible, vulnérabilités connues détectées avant publication |

### 4. Exploitation

- `ENTRYPOINT` en forme exec : uvicorn reçoit `SIGTERM` (arrêt mesuré : 0,5 s) ; `init: true` dans Compose.
- `HEALTHCHECK` sur `/health` en Python (pas de `curl` dans l'image) ; Container Apps utilise ses propres sondes `/health` et `/health/ready`.
- Étiquettes OCI (`org.opencontainers.image.version`, `revision`, `created`, `source`, `licenses`) passées en `--build-arg` par la CI.
- `docker-compose.yml` = exécution locale de l'image de production, avec les mêmes durcissements que la cible Azure.

## Conséquences

- Mettre à jour une dépendance = régénérer `requirements/prod.lock` et `test.lock` (commande dans le [guide](../docker.md)) ; changer de version de scikit-learn impose de **réentraîner** et publier une nouvelle version du modèle.
- Le système de fichiers étant en lecture seule, **`/data` doit être un volume** tant que SQLite est utilisé ; sans volume, le démarrage échoue (`sqlite3.OperationalError`). En test/prod, la base PostgreSQL prévue par l'ADR-0003 supprimera ce besoin.
- L'image ne contient pas de modèle : `/health/ready` renvoie 503 tant qu'aucun modèle n'est monté (comportement voulu, l'orchestrateur n'envoie pas de trafic).
- La documentation interactive n'est disponible que si `APP_ENV=dev` (Compose local par défaut).
- Pistes : publication par la CI (GitHub Actions → Azure Container Registry), signature de l'image (cosign / Notation), SBOM (`docker buildx build --sbom=true`), `PostgresOrderStore`.

Related: [ADR-0002](ADR-0002-stockage-artefacts-modele.md) · [ADR-0003](ADR-0003-hebergement-plateforme-deploiement.md) · [ADR-0004](ADR-0004-strategie-deploiement-blue-green.md) · [ADR-0005](ADR-0005-securite-entrees-sorties.md) · [ADR-0006](ADR-0006-securite-acces-donnee.md) · [ADR-0007](ADR-0007-suivi-experiences-mlflow.md) · [Guide Docker](../docker.md) · [Journal Docker](../journal/2026-10-26-image-docker.md)
