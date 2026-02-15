from fastapi.testclient import TestClient

from retail_risk_aug.api.app import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/admin/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_alerts_and_alert_detail_endpoints() -> None:
    client = TestClient(create_app())
    alerts_response = client.get("/alerts", params={"status": "open"})
    assert alerts_response.status_code == 200
    alerts = alerts_response.json()
    assert alerts

    case_id = alerts[0]["case_id"]
    detail_response = client.get(f"/alert/{case_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["alert"]["case_id"] == case_id


def test_similarity_and_graph_endpoints() -> None:
    client = TestClient(create_app())
    alerts = client.get("/alerts", params={"status": "open"}).json()
    txn_id = alerts[0]["txn_id"]

    similar_response = client.get(f"/similar/transaction/{txn_id}", params={"k": 10})
    assert similar_response.status_code == 200

    graph_response = client.get(f"/graph/txn/{txn_id}")
    assert graph_response.status_code == 200
    assert graph_response.json()["txn_id"] == txn_id
