"""Test d'intégration de l'adaptateur MLflow (base SQLite temporaire)."""
import pytest

mlflow = pytest.importorskip("mlflow")

# Imports après importorskip : le module est ignoré si MLflow est absent
# pylint: disable=wrong-import-position
from express_delivery.ml.dataset import clean_orders_data, generate_orders_dataset  # noqa: E402
from tests.conftest import build_test_trainer  # noqa: E402


def test_mlflow_tracker_records_params_metrics_and_model(tmp_path, monkeypatch):
    # MLflow est facultatif (importorskip plus haut) : import local voulu
    # pylint: disable-next=import-outside-toplevel
    from express_delivery.infrastructure.tracking.mlflow_tracker import MlflowExperimentTracker

    monkeypatch.chdir(tmp_path)  # les artefacts MLflow (mlruns/) restent dans le dossier temporaire
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    tracker = MlflowExperimentTracker(uri, "test-livraison-express")
    data = clean_orders_data(generate_orders_dataset(n_rows=500))

    result = build_test_trainer(tracker).train(data, run_name="it", tags={"model_version": "9.9.9"})

    run = mlflow.MlflowClient(uri).get_run(result.run_id)
    assert run.data.metrics["roc_auc"] == pytest.approx(result.metrics["roc_auc"])
    assert run.data.params["model_type"] == "LogisticRegression"
    assert run.data.tags["model_version"] == "9.9.9"
    reloaded = mlflow.sklearn.load_model(f"runs:/{result.run_id}/model")
    assert hasattr(reloaded, "predict_proba")
