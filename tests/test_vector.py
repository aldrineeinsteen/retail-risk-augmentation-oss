from datetime import UTC, datetime

from retail_risk_aug.models import Transaction
from retail_risk_aug.vector import build_index


def test_vector_similarity_returns_expected_neighbor() -> None:
    txns = [
        Transaction(
            txn_id="t1",
            ts=datetime(2025, 1, 1, tzinfo=UTC),
            account_id="a1",
            counterparty_account_id="a2",
            merchant_id="m1",
            amount=100.0,
            channel="ONLINE",
            txn_type="ONLINE_PURCHASE",
            device_id="d1",
            ip="10.0.0.1",
            geo="US-NY",
            narrative="n1",
        ),
        Transaction(
            txn_id="t2",
            ts=datetime(2025, 1, 1, 0, 1, tzinfo=UTC),
            account_id="a3",
            counterparty_account_id="a4",
            merchant_id="m2",
            amount=110.0,
            channel="ONLINE",
            txn_type="ONLINE_PURCHASE",
            device_id="d2",
            ip="10.0.0.2",
            geo="US-NY",
            narrative="n2",
        ),
        Transaction(
            txn_id="t3",
            ts=datetime(2025, 1, 1, 0, 2, tzinfo=UTC),
            account_id="a5",
            counterparty_account_id="a6",
            merchant_id="m3",
            amount=9000.0,
            channel="BRANCH",
            txn_type="BILL_PAYMENT",
            device_id="d9",
            ip="10.0.0.3",
            geo="US-CA",
            narrative="n3",
        ),
    ]

    index = build_index(txns)
    results = index.search_similar("t1", k=2)

    assert results
    assert results[0].txn_id == "t2"
