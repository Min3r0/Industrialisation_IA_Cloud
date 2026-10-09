"""Le code doit respecter openapi.yml pour toutes les opérations livrées (x-session <= SESSION)."""
from pathlib import Path

import pytest
import yaml

SESSION = 2
CONTRACT = yaml.safe_load((Path(__file__).parents[1] / "openapi.yml").read_text(encoding="utf-8"))
EXPECTED = [
    (path, method, operation)
    for path, item in CONTRACT["paths"].items()
    for method, operation in item.items()
    if operation.get("x-session", 99) <= SESSION
]


@pytest.mark.parametrize("path,method,operation", EXPECTED, ids=[f"{m.upper()} {p}" for p, m, _ in EXPECTED])
def test_operation_matches_contract(client, path, method, operation):
    generated = client.app.openapi()["paths"].get(path, {}).get(method)
    assert generated is not None, f"{method.upper()} {path} absent du code"
    assert generated["operationId"] == operation["operationId"]
    assert set(generated["responses"]) == set(operation["responses"])


def test_order_features_required_fields_match(client):
    expected = set(CONTRACT["components"]["schemas"]["OrderFeatures"]["required"])
    generated = client.app.openapi()["components"]["schemas"]["OrderFeatures"]
    assert set(generated["required"]) == expected
    assert generated["additionalProperties"] is False
