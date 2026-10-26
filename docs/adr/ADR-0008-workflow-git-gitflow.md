---
title: ADR-0008 — Workflow Git (Gitflow) et fichiers de collaboration
date: 2026-10-26
tags: [adr, git, gitflow, github, collaboration, licence]
aliases: [ADR-0008, Gitflow, Workflow Git]
status: Accepté
---

# ADR-0008 — Workflow Git (Gitflow) et fichiers de collaboration

**Status :** Accepté
**Date :** 26/10/2026

## Contexte

- Le dépôt GitHub `Min3r0/Industrialisation_IA_Cloud` existe avec une seule branche, `main`, sur laquelle tous les commits sont poussés directement.
- Le projet doit pouvoir accueillir d'autres contributeurs et livrer des versions identifiables (le déploiement Blue / Green de l'[ADR-0004](ADR-0004-strategie-deploiement-blue-green.md) bascule d'une version à une autre).
- Il manque les fichiers attendus d'un dépôt collaboratif : README orienté GitHub, guide de contribution, licence, politique de sécurité, code de conduite.
- Le dossier `correction/` (code de l'intervenant) et les PDF du cours ne nous appartiennent pas.

## Options considérées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. Tout sur `main` (existant) | Aucun effort | Pas de revue, pas de version stable identifiable |
| B. GitHub Flow (`main` + branches courtes) | Simple, adapté au déploiement continu | Pas de branche d'intégration ni de préparation de version |
| C. **Gitflow** (`main`, `develop`, `feature/*`, `release/*`, `hotfix/*`) | Versions taguées sur `main`, intégration sur `develop`, correctifs urgents isolés ; demandé par le cours | Plus de branches et de fusions à gérer |
| D. Trunk-based development | Intégration très fréquente | Suppose une CI mûre et des feature flags |

## Décision

**Option C — Gitflow**, appliqué avec des pull requests (pas de fusion locale directe sur les branches protégées).

1. **Branches** : `main` (production, chaque fusion taguée `vX.Y.Z`), `develop` (intégration), `feature/<sujet>` depuis `develop`, `release/<X.Y.Z>` et `hotfix/<X.Y.Z>` fusionnées dans `main` **et** `develop`.
2. **Protection** (règles GitHub sur `main` et `develop`) : pull request obligatoire, au moins une approbation (désactivable tant que le projet n'a qu'un contributeur), pas de push forcé ni de suppression.
3. **Fusions** : squash pour `feature/*`, merge commit pour `release/*` et `hotfix/*`.
4. **Commits** : Conventional Commits (`feat`, `fix`, `docs`…).
5. **Versions** : versionnage sémantique ; la version du code (`pyproject.toml`, tag) est indépendante de la version du modèle (`MODEL_VERSION`, [ADR-0002](ADR-0002-stockage-artefacts-modele.md)).
6. **Fichiers de collaboration** à la racine : `README.md`, `CONTRIBUTING.md`, `LICENSE` (MIT), `SECURITY.md` (signalement privé GitHub), `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 traduit), et `.github/` (modèle de pull request, modèles d'issues).
7. **Contenu publié** : `correction/` et les PDF du cours sont exclus (`.gitignore`) ; le notebook d'origine reste versionné comme source de l'industrialisation. Le journal et `INDEX.md` (vault Obsidian) restent hors dépôt ; le `README.md` devient la vitrine GitHub, sans frontmatter.

## Conséquences

- Plus de commit direct sur `main` : chaque changement passe par une branche et une pull request, ce qui laisse une trace de revue.
- La procédure de version (branche `release/*`, tag, report dans `develop`) est décrite dans `CONTRIBUTING.md`.
- Une future CI (GitHub Actions : `pytest` sur chaque pull request) pourra devenir une condition de fusion des règles de protection.
- Les tags `vX.Y.Z` servent de référence aux images déployées en Blue / Green.
- Si `correction/` avait déjà été poussé, il reste dans l'historique : seul le retirer de l'index (`git rm -r --cached`) l'exclut des versions suivantes.

Related: [ADR-0004](ADR-0004-strategie-deploiement-blue-green.md) · [ADR-0006](ADR-0006-securite-acces-donnee.md) · [Architecture](../architecture.md) · [Journal du 26/10](../journal/2026-10-26-github-gitflow.md)
