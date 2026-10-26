# Contribuer

Merci de votre intérêt pour le projet. Ce guide décrit comment proposer une modification : branches, commits, tests et pull requests.

En participant, vous acceptez de respecter le [Code de conduite](CODE_OF_CONDUCT.md).

## Sommaire

- [Signaler un bug ou proposer une idée](#signaler-un-bug-ou-proposer-une-idée)
- [Préparer son environnement](#préparer-son-environnement)
- [Workflow Git : Gitflow](#workflow-git--gitflow)
- [Messages de commit](#messages-de-commit)
- [Règles de code](#règles-de-code)
- [Tests](#tests)
- [Pull requests](#pull-requests)
- [Publier une version](#publier-une-version)
- [Décisions d'architecture (ADR)](#décisions-darchitecture-adr)

## Signaler un bug ou proposer une idée

1. Vérifiez qu'une [issue](https://github.com/Min3r0/Industrialisation_IA_Cloud/issues) n'existe pas déjà.
2. Ouvrez une issue avec le modèle adapté (**Bug** ou **Évolution**) : étapes pour reproduire, comportement attendu, version de Python et du modèle servi (`MODEL_VERSION`).
3. Une **faille de sécurité** ne se signale jamais dans une issue : suivez [SECURITY.md](SECURITY.md).

## Préparer son environnement

```bash
git clone https://github.com/Min3r0/Industrialisation_IA_Cloud.git
cd Industrialisation_IA_Cloud
git switch develop
python -m venv .venv
# Windows : .venv\Scripts\Activate.ps1   |   Linux/macOS : source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Tous les tests doivent passer avant de commencer.

## Workflow Git : Gitflow

Le choix est expliqué dans l'[ADR-0008](docs/adr/ADR-0008-workflow-git-gitflow.md).

| Branche | Créée depuis | Fusionnée dans | Rôle |
|---|---|---|---|
| `main` | — | — | Code en production. Chaque commit est une version taguée `vX.Y.Z`. **Protégée.** |
| `develop` | `main` | — | Intégration de la prochaine version. **Protégée.** |
| `feature/<sujet>` | `develop` | `develop` | Nouvelle fonctionnalité, refactoring, documentation |
| `release/<X.Y.Z>` | `develop` | `main` **et** `develop` | Préparation d'une version : numéro, derniers correctifs, aucune nouvelle fonctionnalité |
| `hotfix/<X.Y.Z>` | `main` | `main` **et** `develop` | Correction urgente d'une version en production |

### Nommage

- En minuscules, mots séparés par des tirets : `feature/cle-api-rotation`, `feature/42-export-csv` (le numéro d'issue est conseillé).
- `release/` et `hotfix/` portent le numéro de version visé : `release/1.2.0`, `hotfix/1.1.1`.

### Développer une fonctionnalité

```bash
git switch develop
git pull
git switch -c feature/mon-sujet
# ... commits ...
git push -u origin feature/mon-sujet
# puis ouvrir une pull request vers develop
```

Gardez votre branche à jour avec `develop` (`git pull --rebase origin develop` tant que la branche n'est partagée avec personne, sinon `git merge develop`).

### Avec l'extension git-flow (facultatif)

Les commandes ci-dessus suffisent. Si vous préférez l'extension [git-flow](https://github.com/nvie/gitflow) (incluse dans Git for Windows) :

```bash
git flow init -d                     # main / develop, préfixes feature/ release/ hotfix/, tags v
git flow feature start mon-sujet
git flow feature publish mon-sujet   # puis pull request vers develop
```

Préférez une pull request à `git flow feature finish` : la fusion doit passer par la revue.

## Messages de commit

Format [Conventional Commits](https://www.conventionalcommits.org/fr/v1.0.0/) :

```text
<type>(<portée facultative>): <résumé à l'impératif, 72 caractères max>

<corps facultatif : le pourquoi, pas le comment>

Refs #<issue>
```

| Type | Usage |
|---|---|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `docs` | Documentation, ADR |
| `refactor` | Changement de code sans changement de comportement |
| `test` | Ajout ou modification de tests |
| `build` | Dépendances, `pyproject.toml`, image Docker |
| `ci` | Intégration continue |
| `chore` | Maintenance (gitignore, outillage) |

Exemples : `feat(api): ajoute la route GET /v1/models`, `fix(security): refuse une clé expirée le jour même`, `docs(adr): ajoute l'ADR-0008 Gitflow`.

Un changement incompatible (contrat d'API, format de `manifest.json`) est signalé par `!` après le type et une ligne `BREAKING CHANGE:` dans le corps.

## Règles de code

Le projet applique les principes **SOLID** et une architecture **ports et adaptateurs** (voir [docs/architecture.md](docs/architecture.md)) :

- **S** : une classe = une responsabilité (ex. `TrainTestSplitter`, `ModelEvaluator`).
- **O** : ajouter un comportement par une nouvelle implémentation d'un port (`OrderStore`, `ExperimentTracker`…), pas en modifiant le code existant.
- **L** : toute implémentation d'un port doit pouvoir remplacer les autres (mêmes tests).
- **I** : des ports petits et ciblés dans `abstractions/`.
- **D** : le code métier dépend des abstractions ; le choix des implémentations se fait uniquement dans les *composition roots* (`api/app.py`, `scripts/train.py`).

Et aussi :

- `domain/` n'importe ni FastAPI, ni scikit-learn, ni MLflow.
- L'API n'importe jamais MLflow (dépendance d'entraînement, [ADR-0007](docs/adr/ADR-0007-suivi-experiences-mlflow.md)).
- Pas de `Settings()` créé au fond d'une classe ni de singleton : les dépendances arrivent par le constructeur.
- Noms explicites, fonctions courtes, annotations de type, docstrings sur les éléments publics.
- Toute route ajoutée ou modifiée l'est d'abord dans [`openapi.yml`](openapi.yml) (le test de contrat le vérifie).
- Aucun secret, clé d'API, donnée client ou fichier `.env` dans un commit.

## Tests

```bash
pytest
```

- Chaque correction de bug arrive avec un test qui échouait avant.
- Chaque nouvelle classe a ses tests unitaires ; utiliser les doubles de `tests/fakes.py` et `InMemoryOrderStore` plutôt que des services réels.
- Un changement du modèle (pipeline, données, graine) indique dans la pull request les métriques avant / après (accuracy, F1, ROC AUC).

## Pull requests

1. Une pull request = un sujet. Cible : `develop` (sauf `release/*` et `hotfix/*`, voir ci-dessous).
2. Remplissez le modèle de description (contexte, changements, tests, ADR concernée).
3. Conditions de fusion :
   - les tests passent ;
   - au moins une relecture approuvée ;
   - la branche est à jour avec sa cible ;
   - la documentation (README, architecture, ADR) est mise à jour si le comportement change.
4. Fusion par **squash** pour les `feature/*` (un commit propre par fonctionnalité dans `develop`) ; **merge commit** pour `release/*` et `hotfix/*` (pour garder le lien entre `main` et `develop`).
5. Supprimez la branche après fusion.

## Publier une version

Le projet suit le [versionnage sémantique](https://semver.org/lang/fr/) : `MAJEUR.MINEUR.CORRECTIF`.

```bash
# 1. Préparer
git switch develop && git pull
git switch -c release/1.2.0
# mettre à jour version dans pyproject.toml, commit "build: version 1.2.0"
git push -u origin release/1.2.0
# 2. Pull request release/1.2.0 -> main, relecture, fusion (merge commit)
# 3. Taguer main
git switch main && git pull
git tag -a v1.2.0 -m "Version 1.2.0"
git push origin v1.2.0
# 4. Reporter dans develop (pull request main -> develop ou fusion de release/1.2.0 dans develop)
```

Un **hotfix** suit le même chemin depuis `main` : `git switch -c hotfix/1.1.1 main`, correction, pull request vers `main`, tag `v1.1.1`, puis report dans `develop`.

La version du **code** (`pyproject.toml`, tag Git) est distincte de la version du **modèle** (`artifacts/models/<X.Y.Z>`, `MODEL_VERSION`) : un nouvel entraînement n'impose pas une nouvelle version du code, et inversement.

## Décisions d'architecture (ADR)

Un choix structurant (stockage, sécurité, déploiement, nouvelle dépendance importante) fait l'objet d'une ADR dans `docs/adr/` :

- nom `ADR-XXXX-sujet-en-kebab-case.md`, numéro suivant ;
- sections : Contexte, Options considérées, Décision, Conséquences ;
- une ADR acceptée ne se modifie pas : on en écrit une nouvelle qui la complète ou la remplace, et on met à jour le statut de l'ancienne.
