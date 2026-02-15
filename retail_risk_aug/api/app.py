from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from retail_risk_aug.app_state import AppState, build_default_app_state


def create_app(state: AppState | None = None) -> FastAPI:
    app = FastAPI(title="Retail Risk Augmentation API", version="0.1.0")
    app_state = state or build_default_app_state()
    app.state.risk_state = app_state

    @app.get("/admin/health")
    def admin_health() -> dict[str, object]:
        runtime_state: AppState = app.state.risk_state
        return {
            "status": "ok",
            "transactions": len(runtime_state.dataset.transactions),
            "alerts": len(runtime_state.alerts),
            "vector_backend": runtime_state.vector_index.backend,
            "graph_nodes": runtime_state.graph.graph.number_of_nodes(),
        }

    @app.get("/alerts")
    def list_alerts(status: str = Query(default="open")) -> list[dict[str, object]]:
        runtime_state: AppState = app.state.risk_state
        return [alert.model_dump(mode="json") for alert in runtime_state.list_alerts(status=status)]

    @app.get("/alert/{case_id}")
    def get_alert(case_id: str) -> dict[str, object]:
        runtime_state: AppState = app.state.risk_state
        alert = runtime_state.get_alert(case_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="alert not found")

        txn = runtime_state.get_transaction(alert.txn_id)
        similar = runtime_state.get_similar_transactions(alert.txn_id, k=10)
        return {
            "alert": alert.model_dump(mode="json"),
            "transaction": txn.model_dump(mode="json") if txn else None,
            "similar": [item.model_dump(mode="json") for item in similar],
        }

    @app.get("/similar/transaction/{txn_id}")
    def similar_transaction(txn_id: str, k: int = Query(default=10, ge=1, le=100)) -> list[dict[str, object]]:
        runtime_state: AppState = app.state.risk_state
        txn = runtime_state.get_transaction(txn_id)
        if txn is None:
            raise HTTPException(status_code=404, detail="transaction not found")
        similar = runtime_state.get_similar_transactions(txn_id, k)
        return [item.model_dump(mode="json") for item in similar]

    @app.get("/graph/txn/{txn_id}")
    def graph_for_transaction(txn_id: str) -> dict[str, object]:
        runtime_state: AppState = app.state.risk_state
        txn = runtime_state.get_transaction(txn_id)
        if txn is None:
            raise HTTPException(status_code=404, detail="transaction not found")

        neighborhood = runtime_state.graph.neighborhood(account_id=txn.account_id, hops=2)
        return {
            "txn_id": txn_id,
            "account_id": txn.account_id,
            "neighborhood": neighborhood,
        }

    return app


app = create_app()
