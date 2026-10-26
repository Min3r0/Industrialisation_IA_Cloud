"""Construction de la pipeline scikit-learn non entraînée (cellules 22 à 24 du notebook)."""
from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from express_delivery.domain.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES


class PipelineFactory:
    """Seule responsabilité : décrire le prétraitement et le classifieur."""

    MODEL_TYPE = "LogisticRegression"

    def __init__(self, random_state: int = 42, max_iter: int = 1000) -> None:
        self._random_state = random_state
        self._max_iter = max_iter

    @property
    def params(self) -> dict[str, object]:
        """Hyperparamètres, transmis tels quels à l'outil de suivi."""
        return {
            "model_type": self.MODEL_TYPE,
            "max_iter": self._max_iter,
            "class_weight": "balanced",
            "random_state": self._random_state,
        }

    def build(self) -> Pipeline:
        numeric = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])
        categorical = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ])
        preprocessor = ColumnTransformer([
            ("numeric", numeric, list(NUMERIC_FEATURES)),
            ("categorical", categorical, list(CATEGORICAL_FEATURES)),
        ])
        classifier = LogisticRegression(
            max_iter=self._max_iter, class_weight="balanced", random_state=self._random_state
        )
        return Pipeline([("preprocessor", preprocessor), ("classifier", classifier)])
