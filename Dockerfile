# syntax=docker/dockerfile:1.7
#
# Image de l'API d'éligibilité à la livraison express (ADR-0009).
#
#   builder : installe les dépendances (verrouillées, avec empreintes) dans /opt/venv
#   test    : builder + outils de test, lance pytest (cible facultative, utilisée par la CI)
#   runtime : image finale, sans compilateur, sans pip, sans modèle, sans secret,
#             exécutée par un utilisateur non root
#
#   docker build -t express-delivery:1.0.0 .
#   docker build --target test .
#
# En CI, épingler l'image de base par empreinte (voir docs/docker.md) :
#   --build-arg PYTHON_IMAGE=python:3.13-slim-trixie@sha256:<empreinte>

ARG PYTHON_IMAGE=python:3.13-slim-trixie

# ---------------------------------------------------------------------------
# 1. builder : dépendances et paquet de l'application dans un environnement virtuel
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_INPUT=1 \
    PIP_ROOT_USER_ACTION=ignore \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# venv sans pip : c'est le pip de l'image de base qui installe dedans (--python),
# l'environnement copié dans l'image finale ne contient donc aucun installeur.
RUN python -m venv --without-pip /opt/venv

WORKDIR /build

# Couche 1 (change rarement) : dépendances tierces, versions et empreintes SHA-256 imposées.
# Le cache BuildKit évite de retélécharger les roues d'un build à l'autre.
COPY requirements/prod.lock requirements/prod.lock
RUN --mount=type=cache,target=/root/.cache/pip \
    pip --python /opt/venv/bin/python install \
        --require-hashes --no-deps --only-binary=:all: \
        -r requirements/prod.lock

# Couche 2 (change souvent) : le code de l'application, installé comme un paquet normal.
COPY pyproject.toml ./
COPY src ./src
RUN pip --python /opt/venv/bin/python install --no-deps --no-cache-dir . \
 # Allègement : suites de tests embarquées par numpy, pandas, scipy, scikit-learn…
 && find /opt/venv -depth -type d -name tests -path '*/site-packages/*/*' -exec rm -rf {} + \
 # … et fichiers inutiles à l'exécution (sources Cython, en-têtes C, métadonnées de build)
 && find /opt/venv \( -name '*.pyx' -o -name '*.pxd' -o -name '*.pyi' \
        -o -name '*.c' -o -name '*.h' -o -name '*.cpp' \) -type f -delete

# ---------------------------------------------------------------------------
# 2. test : exécute la suite de tests contre les dépendances réellement embarquées
# ---------------------------------------------------------------------------
FROM builder AS test

COPY requirements/test.lock requirements/test.lock
RUN --mount=type=cache,target=/root/.cache/pip \
    pip --python /opt/venv/bin/python install \
        --require-hashes --no-deps --only-binary=:all: \
        -r requirements/test.lock
COPY openapi.yml ./
COPY tests ./tests
RUN python -m pytest -q -p no:cacheprovider

# ---------------------------------------------------------------------------
# 3. runtime : image de production
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

ARG APP_VERSION=1.0.0
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="express-delivery" \
      org.opencontainers.image.description="API d'éligibilité à la livraison express" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/Min3r0/Industrialisation_IA_Cloud" \
      org.opencontainers.image.licenses="MIT"

# Configuration par défaut : production, donc authentification obligatoire et /docs masqué
# (config.py refuse de démarrer en prod sans AUTH_ENABLED, ADR-0006).
# Le modèle n'est PAS dans l'image : il est monté en lecture seule sur /models (ADR-0003).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    APP_ENV=prod \
    MODELS_DIR=/models \
    DATABASE_PATH=/data/orders.db

# Surface d'attaque réduite : pas de pip/setuptools dans l'image finale,
# utilisateur système sans shell ni répertoire personnel, UID/GID fixes (> 10000).
RUN python -m pip uninstall --yes --quiet pip setuptools wheel 2>/dev/null || true \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin app \
 && install -d -o app -g app -m 0750 /data \
 && install -d -o root -g app -m 0750 /models

# Le code appartient à root et n'est pas modifiable par l'utilisateur qui l'exécute.
COPY --from=builder --chown=root:root /opt/venv /opt/venv

WORKDIR /data
USER 10001:10001
EXPOSE 8000

# Sonde de vivacité locale (Docker / Compose). En production, Azure Container Apps
# utilise ses propres sondes sur /health et /health/ready (ADR-0003).
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

# Forme exec : uvicorn est le PID 1 et reçoit directement SIGTERM (arrêt propre en Blue/Green).
# --no-server-header : ne divulgue pas le serveur ni sa version (ADR-0005).
ENTRYPOINT ["uvicorn", "express_delivery.main:app", "--host", "0.0.0.0", "--port", "8000", \
            "--no-server-header"]
