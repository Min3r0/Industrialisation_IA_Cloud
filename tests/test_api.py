from tests.conftest import EASY_ORDER, HARD_ORDER


def test_health(client):
    assert client.get("/health").json() == {
        "status": "ok", "service": "eligibilite-livraison-express", "version": "1.0.0"}


def test_ready_when_model_loaded(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"model": "loaded", "order_store": "reachable"}


def test_not_ready_without_model(client_without_model):
    response = client_without_model.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert client_without_model.get("/health").status_code == 200  # vivacité indépendante


def test_create_then_get_order(client):
    response = client.post("/v1/orders", json={**EASY_ORDER, "order_id": "CMD-000001"})
    assert response.status_code == 202
    assert response.json() == {"order_id": "CMD-000001", "status": "accepted"}
    assert client.get("/v1/orders/CMD-000001").json() == {**EASY_ORDER, "order_id": "CMD-000001"}


def test_order_id_is_generated_when_absent(client):
    order_id = client.post("/v1/orders", json=EASY_ORDER).json()["order_id"]
    assert order_id.startswith("CMD-")
    assert client.get(f"/v1/orders/{order_id}").status_code == 200


def test_unknown_order_returns_404_error(client):
    response = client.get("/v1/orders/absent")
    assert response.status_code == 404
    assert response.json()["error"] == "order_not_found"


def test_missing_feature_returns_422_error(client):
    body = {k: v for k, v in EASY_ORDER.items() if k != "distance_km"}
    response = client.post("/v1/predictions", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"
    assert any("distance_km" in detail for detail in response.json()["details"])


def test_extra_feature_returns_422(client):
    assert client.post("/v1/orders", json={**EASY_ORDER, "color": "red"}).status_code == 422


def test_out_of_range_value_returns_422(client):
    assert client.post("/v1/predictions", json={**EASY_ORDER, "carrier_capacity": 1.5}).status_code == 422
    assert client.post("/v1/predictions", json={**EASY_ORDER, "weather": "tempete"}).status_code == 422


def test_prediction(client):
    response = client.post("/v1/predictions", json={**EASY_ORDER, "order_id": "CMD-9"})
    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == "CMD-9" and body["decision"] == "oui"
    assert client.post("/v1/predictions", json=HARD_ORDER).json()["decision"] == "non"


def test_prediction_without_model_returns_503(client_without_model):
    response = client_without_model.post("/v1/predictions", json=EASY_ORDER)
    assert response.status_code == 503
    assert response.json()["error"] == "model_unavailable"
