# Politique de sécurité

## Versions prises en charge

Seule la dernière version publiée sur `main` (dernier tag `vX.Y.Z`) reçoit des correctifs de sécurité.

| Version | Prise en charge |
|---|---|
| Dernier tag `vX.Y.Z` sur `main` | Oui |
| Versions antérieures | Non |
| Branches `develop`, `feature/*` | Non (pas de garantie, code en cours) |

## Signaler une vulnérabilité

**N'ouvrez pas d'issue publique**, ne publiez pas de pull request ni de message qui décrit la faille.

1. Utilisez le signalement privé de GitHub : onglet **Security** → **Report a vulnerability** ([lien direct](https://github.com/Min3r0/Industrialisation_IA_Cloud/security/advisories/new)).
2. Indiquez :
   - la version (tag ou commit) et la configuration concernées (`APP_ENV`, `AUTH_ENABLED`…) ;
   - la route ou le composant touché ;
   - les étapes pour reproduire, et une preuve de concept minimale si possible ;
   - l'impact estimé (accès à des commandes, contournement de clé d'API, extraction du modèle…).
3. Ne joignez **jamais** de vraie clé d'API, de secret ou de donnée client : remplacez-les par des valeurs fictives.

## Ce à quoi vous attendre

| Étape | Délai visé |
|---|---|
| Accusé de réception | 5 jours ouvrés |
| Première évaluation (confirmée ou non, gravité) | 10 jours ouvrés |
| Correctif publié (`hotfix/X.Y.Z` puis tag) | selon la gravité, au plus tôt |

Projet d'étude maintenu sur le temps libre : ces délais sont des objectifs, pas un engagement contractuel. Vous serez tenu informé de l'avancement et crédité dans l'avis de sécurité si vous le souhaitez.

## Périmètre

Dans le périmètre :

- l'API (`src/express_delivery/api`) : authentification par clé d'API, rôles, limitation de débit ([ADR-0005](docs/adr/ADR-0005-securite-entrees-sorties.md), [ADR-0006](docs/adr/ADR-0006-securite-acces-donnee.md)) ;
- la validation des entrées et l'exposition d'informations dans les réponses d'erreur ;
- le chargement des artefacts de modèle ([ADR-0002](docs/adr/ADR-0002-stockage-artefacts-modele.md)) ;
- les scripts `scripts/` (génération de clés, entraînement).

Hors périmètre :

- une configuration volontairement non sécurisée en dev (`AUTH_ENABLED=false`, `/docs` exposé) ;
- les vulnérabilités des dépendances déjà publiées sans exploitation propre au projet (signalez-les plutôt en issue normale pour une mise à jour) ;
- les attaques par déni de service volumétrique.

## Bonnes pratiques pour les contributeurs

- Aucun secret dans Git : variables d'environnement, fichiers `.env` ignorés, Key Vault en production.
- Seule l'**empreinte** SHA-256 d'une clé d'API est stockée, jamais la clé.
- Une clé exposée par erreur (commit, log, capture) est **révoquée** immédiatement : la supprimer de `API_KEYS` et en générer une nouvelle avec `scripts/create_api_key.py`. Réécrire l'historique Git ne suffit pas.
- Ne charger un fichier de modèle (`joblib`, `pickle`) que depuis une source de confiance : la désérialisation peut exécuter du code.
