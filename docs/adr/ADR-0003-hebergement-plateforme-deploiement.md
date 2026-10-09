---
title: ADR-0003 — Plateforme de déploiement et hébergement
date: 2026-10-09
tags: [adr, architecture, deploiement, cloud, azure, seance-2]
aliases: [ADR-0003, Hébergement, Plateforme de déploiement, Azure Container Apps]
status: Accepté
---

# ADR-0003 — Plateforme de déploiement et hébergement

**Status :** Accepté
**Date :** 09/10/2026
**Séance :** 2

## Contexte

L'application est une **API HTTP** (FastAPI) : ce n'est ni une application mobile (store), ni une application de bureau, ni un plugin. Elle relève donc de la catégorie « serveur local, on-premise ou cloud ». Il faut choisir où elle tourne en test et en production, et avec quels services.

Contraintes connues :

- Un processus Python sans état métier en mémoire : le modèle est chargé au démarrage (ADR-0002), les commandes sont persistées par un `OrderStore` (ADR-0001).
- Deux sondes existent déjà : `/health` (vivacité) et `/health/ready` (disponibilité) — exactement ce qu'un orchestrateur attend.
- La stratégie de déploiement retenue est **Blue / Green** ([ADR-0004](ADR-0004-strategie-deploiement-blue-green.md)) : deux versions doivent pouvoir tourner **en même temps** derrière un répartiteur de charge.
- Données de commandes de clients (potentiellement personnelles) : hébergement dans l'Union européenne (RGPD).
- Équipe réduite, contexte de cours : pas d'administration de serveurs ni de cluster Kubernetes à maintenir.
- Le conteneur Docker est le sujet de la séance 3 : la plateforme doit exécuter une **image de conteneur**.

## Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Local (poste du développeur) | Gratuit, déjà en place | Pas de haute disponibilité, pas accessible aux clients : uniquement l'environnement **dev** |
| B. On-premise (VM + nginx) | Maîtrise totale, données dans nos murs | Matériel, OS, correctifs, sauvegardes, TLS et load balancer à gérer soi-même |
| C. Cloud IaaS (VM Azure / EC2) | Souple | Même charge d'exploitation que B, payée à l'heure |
| D. Cloud Kubernetes (AKS / EKS / GKE) | Standard du marché, toutes les stratégies de déploiement | Cluster à opérer, surdimensionné pour **un** service |
| E. **Cloud conteneurs managés — Azure Container Apps** | Serverless (pas de nœud à gérer), mise à l'échelle automatique y compris à zéro, **révisions + répartition du trafic natives** (Blue/Green, canary), sondes de santé, identité managée, références Key Vault | Dépendance à Azure ; moins de contrôle fin que Kubernetes |
| F. Équivalents AWS (ECS Fargate + ALB) / GCP (Cloud Run) | Fonctionnellement proches de E | Pas d'avantage décisif ; écosystème Microsoft plus courant dans les entreprises clientes (Entra ID, Office) |

## Décision

**Option E — Microsoft Azure, région France Central, avec Azure Container Apps comme plateforme d'exécution.** Le poste local reste l'environnement **dev** (option A).

Services Azure retenus :

| Besoin | Service Azure | Remarque |
|---|---|---|
| Exécuter l'API | **Azure Container Apps** (mode *multiple revisions*) | 1 révision = 1 version de l'image + sa configuration ; min. 1 réplique en prod |
| Stocker les images | **Azure Container Registry** (privé) | Séance 3 (Docker) ; pull par identité managée, sans mot de passe |
| Point d'entrée, clés, quotas | **Azure API Management** | Voir [ADR-0005](ADR-0005-securite-entrees-sorties.md) |
| Secrets (empreintes des clés d'API, chaîne de connexion) | **Azure Key Vault** | Référencés par Container Apps, jamais dans Git ([ADR-0006](ADR-0006-securite-acces-donnee.md)) |
| Commandes clients en prod | **Azure Database for PostgreSQL – Flexible Server** | Remplace SQLite hors dev (voir conséquences) |
| Artefacts du modèle | **Azure Files** monté en lecture seule sur `MODELS_DIR` | Même arborescence que l'ADR-0002 : aucun changement de code |
| Logs et métriques | **Log Analytics** (+ Application Insights en séance 7) | Logs de la console du conteneur |
| Identités | **Identité managée** de l'application | Accès à ACR, Key Vault, PostgreSQL sans secret stocké |

Trois environnements séparés (un *resource group* et un environnement Container Apps chacun) : `dev` (poste local), `test` et `prod` (Azure), configurés uniquement par variables d'environnement (`APP_ENV`, `MODEL_VERSION`, `DATABASE_PATH`/connexion, `AUTH_ENABLED`, `API_KEYS`…).

Pourquoi : c'est l'option qui donne **Blue/Green, sondes, mise à l'échelle, TLS et secrets « sur étagère »** sans cluster à opérer (YAGNI), tout en restant fondée sur un standard portable (image OCI) : migrer vers AKS, Cloud Run ou une VM reste possible sans toucher au code.

## Conséquences

- **ADR-0001 doit évoluer** : avec Blue/Green, deux révisions tournent simultanément et le disque d'un conteneur est éphémère ; SQLite ne convient plus hors dev. Une classe `PostgresOrderStore` sera ajoutée derrière `OrderStore` (principe ouvert/fermé) et une ADR remplacera l'ADR-0001 pour les environnements test/prod.
- Le code ne connaît pas Azure : tout passe par les abstractions existantes et les variables d'environnement. Seul le *composition root* (`api/app.py`) choisira l'implémentation.
- L'image Docker (séance 3) devient le livrable de déploiement ; elle ne doit contenir **ni secret ni modèle** (le modèle vient d'Azure Files).
- Coût récurrent (API Management, PostgreSQL, Log Analytics) à surveiller ; `test` peut descendre à zéro réplique en dehors des heures de travail.
- Dépendance à Azure acceptée ; l'infrastructure devra être décrite en code (Bicep ou Terraform) pour être reproductible — à traiter avec la CI/CD.

Related: [ADR-0004 — Blue / Green](ADR-0004-strategie-deploiement-blue-green.md) · [ADR-0005 — Entrées/sorties](ADR-0005-securite-entrees-sorties.md) · [ADR-0006 — Accès à la donnée](ADR-0006-securite-acces-donnee.md) · [ADR-0001](ADR-0001-stockage-commandes-clients.md) · [ADR-0002](ADR-0002-stockage-artefacts-modele.md) · [Architecture](../architecture.md)
