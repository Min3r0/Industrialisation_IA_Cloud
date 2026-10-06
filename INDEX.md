---
title: Industrialisation de l'IA dans le cloud
date: 2026-10-06
tags: [index, cours, M2EIA, ia, cloud]
---

# Industrialisation de l'IA dans le cloud

Index des notes de cours du M2 EIA. Chaque note est listée ci-dessous avec une ligne qui dit quand la lire.

## Projet

- [README — API éligibilité livraison express](README.md): pour installer, lancer et configurer l'application
- [Architecture de l'application](docs/architecture.md): pour comprendre le découpage SOLID et la correspondance notebook → code

## Décisions d'architecture (ADR)

- [ADR-0001 — Où stocker les commandes clients](docs/adr/ADR-0001-stockage-commandes-clients.md): SQLite derrière `OrderStore`, et quand passer à PostgreSQL
- [ADR-0002 — Où stocker les artefacts du modèle](docs/adr/ADR-0002-stockage-artefacts-modele.md): répertoire local versionné, et quand passer à MLflow Registry

## Journal

- [Journal — Séance 1 (06/10/2026)](docs/journal/2026-10-06-seance-1.md): historique précis des actions et des décisions de la séance 1
