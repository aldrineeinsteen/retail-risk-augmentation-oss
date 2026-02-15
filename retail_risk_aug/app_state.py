from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from retail_risk_aug.generator import generate_dataset
from retail_risk_aug.graph import DevTransactionGraph, build_graph
from retail_risk_aug.models import Alert, Customer, GeneratedDataset, ScoredTransaction, SimilarResult, Transaction
from retail_risk_aug.scoring import score_transactions
from retail_risk_aug.vector import TransactionVectorIndex, build_index, search_similar


@dataclass(slots=True)
class AppState:
    dataset: GeneratedDataset
    scored_transactions: dict[str, ScoredTransaction]
    alerts: dict[str, Alert]
    txn_to_case: dict[str, str]
    txn_by_id: dict[str, Transaction]
    account_to_customer: dict[str, Customer]
    vector_index: TransactionVectorIndex
    graph: DevTransactionGraph

    def list_alerts(self, status: str = "open") -> list[Alert]:
        return [alert for alert in self.alerts.values() if alert.status == status]

    def get_alert(self, case_id: str) -> Alert | None:
        return self.alerts.get(case_id)

    def get_transaction(self, txn_id: str) -> Transaction | None:
        return self.txn_by_id.get(txn_id)

    def get_customer_by_account(self, account_id: str) -> Customer | None:
        return self.account_to_customer.get(account_id)

    def get_case_id_by_txn(self, txn_id: str) -> str | None:
        return self.txn_to_case.get(txn_id)

    def get_transactions_by_account(self, account_id: str, limit: int = 50) -> list[Transaction]:
        items = [txn for txn in self.dataset.transactions if txn.account_id == account_id]
        return sorted(items, key=lambda txn: txn.ts, reverse=True)[:limit]

    def get_similar_transactions(self, txn_id: str, k: int) -> list[SimilarResult]:
        return search_similar(self.vector_index, txn_id=txn_id, k=k)


def build_default_app_state(seed: int = 42) -> AppState:
    dataset = generate_dataset(customers=100, transactions=1000, inject=120, seed=seed)
    scored_list = score_transactions(dataset.transactions)
    scored_map = {item.txn_id: item for item in scored_list}
    txn_by_id = {txn.txn_id: txn for txn in dataset.transactions}

    account_to_customer: dict[str, Customer] = {}
    for customer in dataset.customers:
        account_id = customer.customer_id.replace("C", "A", 1)
        account_to_customer[account_id] = customer

    alerts: dict[str, Alert] = {}
    txn_to_case: dict[str, str] = {}

    for sequence, scored in enumerate(item for item in scored_list if item.score >= 0.75):
        case_id = f"CASE-{sequence + 1:07d}"
        alert = Alert(
            case_id=case_id,
            txn_id=scored.txn_id,
            score=scored.score,
            reason_codes=scored.reason_codes,
            status="open",
            created_ts=datetime.now(tz=UTC),
        )
        alerts[case_id] = alert
        txn_to_case[scored.txn_id] = case_id

    return AppState(
        dataset=dataset,
        scored_transactions=scored_map,
        alerts=alerts,
        txn_to_case=txn_to_case,
        txn_by_id=txn_by_id,
        account_to_customer=account_to_customer,
        vector_index=build_index(dataset.transactions),
        graph=build_graph(dataset.transactions),
    )
