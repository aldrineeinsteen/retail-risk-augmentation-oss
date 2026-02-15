from __future__ import annotations

import networkx as nx

from retail_risk_aug.models import Transaction


class DevTransactionGraph:
    def __init__(self) -> None:
        self.graph = nx.DiGraph()

    @classmethod
    def from_transactions(cls, transactions: list[Transaction]) -> DevTransactionGraph:
        instance = cls()
        for txn in transactions:
            account_node = _node("account", txn.account_id)
            merchant_node = _node("merchant", txn.merchant_id)
            device_node = _node("device", txn.device_id)
            ip_node = _node("ip", txn.ip)

            instance.graph.add_edge(account_node, merchant_node, label="PAID_AT", txn_id=txn.txn_id)
            instance.graph.add_edge(account_node, device_node, label="USES_DEVICE", txn_id=txn.txn_id)
            instance.graph.add_edge(device_node, ip_node, label="SEEN_ON_IP", txn_id=txn.txn_id)

            if txn.counterparty_account_id:
                counterparty_node = _node("account", txn.counterparty_account_id)
                instance.graph.add_edge(account_node, counterparty_node, label="SENT_TO", txn_id=txn.txn_id)

        return instance

    def neighborhood(self, account_id: str, hops: int = 2) -> list[str]:
        source = _node("account", account_id)
        if source not in self.graph:
            return []
        nodes = nx.single_source_shortest_path_length(self.graph, source, cutoff=hops)
        return sorted(nodes.keys())

    def paths(self, account_a: str, account_b: str, max_hops: int) -> list[list[str]]:
        source = _node("account", account_a)
        target = _node("account", account_b)
        if source not in self.graph or target not in self.graph:
            return []
        return [list(path) for path in nx.all_simple_paths(self.graph, source=source, target=target, cutoff=max_hops)]


def build_graph(transactions: list[Transaction]) -> DevTransactionGraph:
    return DevTransactionGraph.from_transactions(transactions)


def _node(node_type: str, value: str) -> str:
    return f"{node_type}:{value}"
