---
title: Guide Docker — construire, lancer, compresser et sécuriser l'image
date: 2026-10-26
tags: [docker, guide, securite, optimisation, seance-3]
aliases: [Guide Docker, Docker]
---

# Guide Docker

Décision et justification : [ADR-0009](adr/ADR-0009-conteneurisation-image-docker.md) · Historique : [Journal Docker](journal/2026-10-26-image-docker.md)

Prérequis : Docker Desktop (Windows / macOS) ou Docker Engine ≥ 24 avec Compose v2 et BuildKit (activés par défaut). Toutes les commandes se lancent **à la racine du projet** ; elles sont identiques en PowerShell et en bash, sauf mention contraire.

## Fichiers

| Fichier | Rôle |
|---|---|
| `Dockerfile` | 3 étapes : `builder` → `test` (facultative) → `runtime` |
| `.dockerignore` | contexte de build en liste blanche |
| `docker-compose.yml` | lancement local de l'image de production, durci |
| `.env.example` | modèle de configuration à copier en `.env` (jamais commité) |
| `requirements/prod.lock` | dépendances de l'API, versions figées + empreintes SHA-256 |
| `requirements/test.lock` | dépendances de test (pytest, httpx, MLflow…), idem |
| `requirements/constraints.txt` | contraintes communes (scikit-learn = version du modèle) |

## Construire et lancer

Il faut au moins un modèle publié dans `artifacts/models/<version>/` (`python scripts/train.py --version 1.1.0` sinon).

```powershell
copy .env.example .env               # bash : cp .env.example .env   (facultatif)
docker compose up --build -d
docker compose ps                    # STATUS doit passer à « (healthy) » en ~20 s
docker compose logs -f api           # Ctrl+C pour quitter les logs
```

Tester (PowerShell : utiliser `curl.exe`, car `curl` y est un alias d'`Invoke-WebRequest`) :

```powershell
curl.exe http://127.0.0.1:8000/health/ready
# http://127.0.0.1:8000/docs dans le navigateur (APP_ENV=dev)
```

Arrêter : `docker compose down` (ajouter `-v` pour effacer aussi le volume des commandes).

### Reproduire la production en local

Dans `.env` :

```dotenv
APP_ENV=prod
AUTH_ENABLED=true
API_KEYS=front:<empreinte>:user:<AAAA-MM-JJ>   # python scripts/create_api_key.py --id front --role user --days 30
```

Puis `docker compose up -d` : `/docs` → 404, `POST /v1/predictions` sans en-tête `X-API-Key` → 401.

### Sans Compose

```bash
docker build -t express-delivery:1.0.0 .
docker run --rm -p 127.0.0.1:8000:8000 \
  --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD/artifacts/models:/models:ro" -v express-data:/data \
  -e APP_ENV=dev -e MODEL_VERSION=1.1.0 express-delivery:1.0.0
```

PowerShell : remplacer `\` par `` ` `` en fin de ligne et `$PWD` par `${PWD}`.

### Lancer les tests dans l'image

```bash
docker build --target test .
```

L'étape échoue si un test échoue : c'est la commande à mettre dans la CI.

## Optimisation

Ce qui est déjà en place (détails dans l'[ADR-0009](adr/ADR-0009-conteneurisation-image-docker.md)) : plusieurs étapes, couche de dépendances séparée du code, cache BuildKit, pas de pip ni d'outils de dev dans l'image finale, élagage des dossiers `tests/` des bibliothèques.

Mesurer chez soi :

```bash
docker images express-delivery                              # taille sur disque
docker history express-delivery:1.0.0                       # poids de chaque couche
docker run --rm --entrypoint sh express-delivery:1.0.0 -c \
  "du -sm /opt/venv/lib/python3.13/site-packages/* | sort -rn | head"
```

Mesures faites le 26/10/2026 (environnement de Claude, image de base de remplacement — à refaire chez soi) :

| Élément | Taille |
|---|---|
| Couche `/opt/venv` (dépendances + application) | 283 Mo sur disque |
| dont scipy / numpy (avec leurs `.libs`) / pandas / scikit-learn | 107 / 51 / 38 / 33 Mo |
| Couche `/opt/venv` compressée (gzip, format par défaut) | 88 Mo |

scipy est le plus gros poste : c'est une dépendance obligatoire de scikit-learn, on ne peut pas l'enlever.

## Compression

Une image est stockée et transférée **couche par couche, compressée** : c'est la taille compressée qui compte pour le registre (Azure Container Registry), le temps de `pull` et donc le temps de démarrage d'une nouvelle révision Blue/Green.

Mesures sur la couche `/opt/venv` (283 Mo non compressés) :

| Algorithme | Taille | Temps de compression | Remarque |
|---|---|---|---|
| gzip niveau 6 (défaut Docker) | 87,9 Mo | 14 s | compatible partout |
| **zstd niveau 3** | **79,7 Mo** (−9 %) | **1,4 s** | décompression plus rapide aussi |
| zstd niveau 19 | 60,3 Mo (−31 %) | 117 s | à réserver aux images publiées rarement |

Publier avec zstd (BuildKit, registre compatible OCI comme Azure Container Registry ; le moteur qui tire l'image doit gérer zstd : Docker ≥ 23, containerd ≥ 1.5) :

```bash
docker buildx build \
  --output type=image,name=<registre>.azurecr.io/express-delivery:1.0.0,push=true,compression=zstd,compression-level=3,force-compression=true,oci-mediatypes=true \
  .
```

Archiver ou transférer une image hors registre :

```bash
docker save express-delivery:1.0.0 | zstd -3 -T0 -o express-delivery-1.0.0.tar.zst
zstd -dc express-delivery-1.0.0.tar.zst | docker load
```

Écarté : `docker export`/`--squash` (on perd le partage des couches entre versions) et les outils de réduction automatique type SlimToolkit (risque de supprimer des modules importés dynamiquement par scikit-learn ou joblib).

## Sécurisation

Mesures intégrées : voir le tableau de l'[ADR-0009](adr/ADR-0009-conteneurisation-image-docker.md). Vérifier qu'elles sont actives :

```bash
docker compose exec api id                                   # uid=10001(app)
docker compose exec api python -m pip --version              # « No module named pip »
docker compose exec api touch /opt/venv/x                    # « Read-only file system »
docker compose exec api grep -E "CapEff|NoNewPrivs" /proc/1/status   # CapEff 0…0, NoNewPrivs 1
curl.exe -si http://127.0.0.1:8000/health                    # pas d'en-tête « server: »
```

### Analyser le Dockerfile (hadolint)

Résultat le 26/10/2026 (hadolint 2.x) : aucun avertissement.


```bash
docker run --rm -i hadolint/hadolint < Dockerfile
```

PowerShell : `Get-Content Dockerfile | docker run --rm -i hadolint/hadolint`.

### Rechercher les vulnérabilités connues (Trivy)

```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image --severity HIGH,CRITICAL --ignore-unfixed express-delivery:1.0.0
```

Sous Windows (Docker Desktop), le socket se monte avec `-v //var/run/docker.sock:/var/run/docker.sock`. Alternative intégrée à Docker Desktop : `docker scout cves express-delivery:1.0.0`. En CI, faire échouer le build sur une vulnérabilité critique corrigeable : `--exit-code 1`.

Vérifier aussi qu'aucun secret n'est entré dans l'image :

```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image --scanners secret express-delivery:1.0.0
```

### Auditer les dépendances Python (pip-audit)

Plus léger que Trivy, ne regarde que les paquets Python du fichier verrouillé (base OSV / PyPI) :

```bash
pip install pip-audit
pip-audit -r requirements/prod.lock --require-hashes --disable-pip
```

Résultat le 26/10/2026 : « No known vulnerabilities found ».

### Épingler l'image de base

Un tag (`python:3.13-slim-trixie`) peut changer de contenu ; une empreinte non. Pour une CI reproductible :

```bash
docker buildx imagetools inspect python:3.13-slim-trixie     # relever « Digest: sha256:… »
docker build --build-arg PYTHON_IMAGE=python:3.13-slim-trixie@sha256:<empreinte> -t express-delivery:1.0.0 .
```

L'empreinte est à mettre à jour régulièrement (correctifs de sécurité de Debian) : Dependabot ou Renovate peuvent le faire automatiquement.

## Mettre à jour les dépendances

Les fichiers `.lock` se régénèrent avec [uv](https://docs.astral.sh/uv/) (`pip install uv`) :

```bash
uv pip compile pyproject.toml -c requirements/constraints.txt \
  --generate-hashes --python-version 3.13 --universal --no-header -o requirements/prod.lock
uv pip compile pyproject.toml --extra dev -c requirements/constraints.txt \
  --generate-hashes --python-version 3.13 --universal --no-header -o requirements/test.lock
docker build --target test .        # vérifier que tout passe
```

Changer `scikit-learn` dans `constraints.txt` impose de réentraîner et de publier une nouvelle version du modèle (ADR-0002).
