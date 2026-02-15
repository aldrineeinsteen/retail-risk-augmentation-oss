from datetime import UTC, datetime

from retail_risk_aug.graph import build_graph
from retail_risk_aug.models import Transaction


def test_graph_neighborhood_and_paths() -> None:
    txns = [
        Transaction(
            txn_id="t1",
            ts=datetime(2025, 1, 1, tzinfo=UTC),
            account_id="a1",
            counterparty_account_id="a2",
            merchant_id="m1",
            amount=10.0,
            channel="MOBILE",
            txn_type="P2P_TRANSFER",
            device_id="d1",
            ip="10.0.0.1",
            geo="US-NY",
            narrative="n1",
        ),
        Transaction(
            txn_id="t2",
            ts=datetime(2025, 1, 1, 0, 1, tzinfo=UTC),
            account_id="a2",
            counterparty_account_id="a3",
            merchant_id="m2",
            amount=20.0,
            channel="MOBILE",
            txn_type="P2P_TRANSFER",
            device_id="d2",
            ip="10.0.0.2",
            geo="US-NY",
            narrative="n2",
        ),
    ]

    graph = build_graph(txns)
    neighborhood = graph.neighborhood("a1", hops=2)
    candidate_paths = graph.paths("a1", "a3", max_hops=3)

    assert "account:a2" in neighborhood
    assert candidate_paths
    assert candidate_paths[0][0] == "account:a1"
    assert candidate_paths[0][-1] == "account:a3"
