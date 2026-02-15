from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph
from streamlit_autorefresh import st_autorefresh

from retail_risk_aug.app_state import AppState, build_default_app_state
from retail_risk_aug.models import Transaction


SQL_OPEN_ALERTS = """
SELECT status, pattern_tag, count(*) AS alert_count
FROM alerts
WHERE status = 'open'
GROUP BY status, pattern_tag
ORDER BY alert_count DESC;
""".strip()


def main() -> None:
    st.set_page_config(page_title="Retail Risk Console", layout="wide")
    st.title("Retail Risk Console")
    state = _get_cached_state()

    _init_ui_state(state)

    if st.session_state.get("next_screen") is not None:
        st.session_state["screen_selector"] = st.session_state["next_screen"]
        st.session_state["next_screen"] = None

    st.sidebar.selectbox(
        "Screen",
        ["Admin dashboard", "Alerts list", "Alert detail", "Transaction detail", "Analyst workbook"],
        key="screen_selector",
    )
    screen = st.session_state["screen_selector"]

    if screen == "Admin dashboard":
        _render_admin_dashboard(state)
    elif screen == "Alerts list":
        _render_alerts_list(state)
    elif screen == "Alert detail":
        _render_alert_detail(state)
    elif screen == "Transaction detail":
        _render_transaction_detail(state)
    else:
        _render_analyst_workbook()


def _render_admin_dashboard(app_state: AppState) -> None:
    st_autorefresh(interval=1000, key="dashboard-refresh")
    _advance_live_cursor(app_state, tick_size=5)

    live_transactions = app_state.dataset.transactions[: st.session_state["live_cursor"]]

    st.subheader("Admin dashboard")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Transactions (live)", len(live_transactions))
    col_b.metric("Open alerts", len(app_state.list_alerts(status="open")))
    col_c.metric("Model version", "v1")
    col_d.metric("Trickle rate", "5 tx/sec")

    if not live_transactions:
        st.info("Waiting for transactions...")
        return

    chart_df = pd.DataFrame(
        [
            {
                "ts": txn.ts,
                "amount": txn.amount,
                "is_injected": int(txn.is_injected),
            }
            for txn in live_transactions
        ]
    )

    st.markdown("### Live transaction flow")
    st.line_chart(chart_df.set_index("ts")["amount"])

    st.markdown("### Injection pattern mix")
    pattern_counts = Counter((txn.pattern_tag.value if txn.pattern_tag else "BASELINE") for txn in live_transactions)
    st.bar_chart(pd.DataFrame({"pattern": list(pattern_counts.keys()), "count": list(pattern_counts.values())}).set_index("pattern"))

    alert_txn_ids = {alert.txn_id for alert in app_state.list_alerts(status="open")}
    baseline_count = sum(1 for txn in live_transactions if txn.txn_id not in alert_txn_ids)
    alerts_count = sum(1 for txn in live_transactions if txn.txn_id in alert_txn_ids)

    st.markdown("### Filter listed items")
    flt_a, flt_b, flt_c = st.columns(3)
    if flt_a.button(f"Baseline ({baseline_count})", key="filter-baseline"):
        st.session_state["dashboard_filter"] = "BASELINE"
    if flt_b.button(f"Alerts ({alerts_count})", key="filter-alerts"):
        st.session_state["dashboard_filter"] = "ALERTS"
    if flt_c.button("All", key="filter-all"):
        st.session_state["dashboard_filter"] = "ALL"

    pattern_cols = st.columns(max(1, min(4, len(pattern_counts))))
    for idx, (pattern_name, count) in enumerate(sorted(pattern_counts.items(), key=lambda item: item[0])):
        if pattern_cols[idx % len(pattern_cols)].button(f"{pattern_name} ({count})", key=f"filter-pattern-{pattern_name}"):
            st.session_state["dashboard_filter"] = pattern_name

    filtered_transactions = _filter_transactions(
        transactions=live_transactions,
        dashboard_filter=st.session_state["dashboard_filter"],
        alert_txn_ids=alert_txn_ids,
    )

    st.caption(f"Filter: {st.session_state['dashboard_filter']} | Showing {len(filtered_transactions)} items")
    if filtered_transactions:
        for txn in filtered_transactions[-40:]:
            pattern = txn.pattern_tag.value if txn.pattern_tag else "BASELINE"
            is_alert = txn.txn_id in alert_txn_ids
            case_id = app_state.get_case_id_by_txn(txn.txn_id)
            customer = app_state.get_customer_by_account(txn.account_id)
            st.markdown(
                f"**{txn.txn_id}** | {txn.ts} | acct={txn.account_id} | merchant={txn.merchant_id} | amount=${txn.amount:,.2f} | pattern={pattern}"
            )
            st.caption(
                f"user={customer.name if customer else 'Unknown'} | risk={customer.risk_band if customer else 'N/A'} | "
                f"alert={'yes' if is_alert else 'no'}"
            )
            col_1, col_2 = st.columns(2)
            if col_1.button("Open transaction detail", key=f"dash-open-txn-{txn.txn_id}"):
                _open_transaction_detail(txn.txn_id)
            if case_id and col_2.button("Open case", key=f"dash-open-case-{case_id}"):
                _open_alert_view(case_id, "Investigate")
            st.divider()

    st.markdown("### Interactive entity graph (live)")
    _render_live_mindmap(live_transactions[-180:])


def _render_alerts_list(app_state: AppState) -> None:
    st.subheader("Alerts list")
    alerts = app_state.list_alerts(status="open")
    for alert in alerts[:50]:
        txn = app_state.get_transaction(alert.txn_id)
        customer = app_state.get_customer_by_account(txn.account_id) if txn else None
        st.markdown(f"**{alert.case_id}** | txn={alert.txn_id} | score={alert.score:.2f}")
        st.caption(
            f"user={customer.name if customer else 'Unknown'} | account={txn.account_id if txn else 'N/A'} | reasons={', '.join(alert.reason_codes)}"
        )
        col_1, col_2, col_3, col_4 = st.columns(4)
        if col_1.button("Investigate", key=f"investigate-{alert.case_id}"):
            _open_alert_view(alert.case_id, "Investigate")
        if col_2.button("Similar", key=f"similar-{alert.case_id}"):
            _open_alert_view(alert.case_id, "Similar")
        if col_3.button("Graph", key=f"graph-{alert.case_id}"):
            _open_alert_view(alert.case_id, "Graph")
        if col_4.button("SQL", key=f"sql-{alert.case_id}"):
            st.session_state["selected_case_id"] = alert.case_id
            st.session_state["next_screen"] = "Analyst workbook"
            st.rerun()
        st.divider()


def _render_alert_detail(app_state: AppState) -> None:
    st.subheader("Alert detail")
    alerts = app_state.list_alerts(status="open")
    alert_ids = [alert.case_id for alert in alerts]
    if not alert_ids:
        st.info("No open alerts.")
        return

    if st.session_state.get("selected_case_id") not in alert_ids:
        st.session_state["selected_case_id"] = alert_ids[0]

    selected_case = st.selectbox("Case", alert_ids, key="selected_case_id")
    alert = app_state.get_alert(selected_case)
    if alert is None:
        st.warning("Alert not found.")
        return

    view = st.radio("View", ["Investigate", "Similar", "Graph", "SQL"], key="alert_view", horizontal=True)

    if view == "Investigate":
        txn = app_state.get_transaction(alert.txn_id)
        customer = app_state.get_customer_by_account(txn.account_id) if txn else None
        st.markdown("### Case summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Case", alert.case_id)
        c2.metric("Score", f"{alert.score:.2f}")
        c3.metric("Status", alert.status)
        c4.metric("Reasons", str(len(alert.reason_codes)))

        st.markdown("### User & transaction context")
        left, right = st.columns(2)
        left.write(
            {
                "customer_id": customer.customer_id if customer else None,
                "customer_name": customer.name if customer else None,
                "segment": customer.segment if customer else None,
                "risk_band": customer.risk_band if customer else None,
                "home_geo": customer.home_geo if customer else None,
            }
        )
        right.write(
            {
                "txn_id": txn.txn_id if txn else None,
                "account_id": txn.account_id if txn else None,
                "merchant_id": txn.merchant_id if txn else None,
                "amount": txn.amount if txn else None,
                "currency": txn.currency if txn else None,
                "channel": txn.channel if txn else None,
                "txn_type": txn.txn_type if txn else None,
                "device_id": txn.device_id if txn else None,
                "ip": txn.ip if txn else None,
                "geo": txn.geo if txn else None,
                "pattern_tag": txn.pattern_tag.value if txn and txn.pattern_tag else "BASELINE",
            }
        )

        with st.expander("Raw JSON"):
            st.json(
                {
                    "alert": alert.model_dump(mode="json"),
                    "transaction": txn.model_dump(mode="json") if txn else None,
                    "customer": customer.model_dump(mode="json") if customer else None,
                }
            )
    elif view == "Similar":
        similar = app_state.get_similar_transactions(alert.txn_id, k=10)
        if not similar:
            st.info("No strong similar transactions found.")
        for item in similar:
            txn = app_state.get_transaction(item.txn_id)
            if txn is None:
                continue
            customer = app_state.get_customer_by_account(txn.account_id)
            case_id = app_state.get_case_id_by_txn(txn.txn_id)
            st.markdown(f"**{txn.txn_id}** | similarity={item.score:.3f} | user={customer.name if customer else 'Unknown'}")
            st.caption(
                f"acct={txn.account_id} | merchant={txn.merchant_id} | amount=${txn.amount:,.2f} | "
                f"channel={txn.channel} | type={txn.txn_type}"
            )
            col_a, col_b = st.columns(2)
            if col_a.button("Open transaction detail", key=f"similar-open-txn-{txn.txn_id}"):
                _open_transaction_detail(txn.txn_id)
            if case_id and col_b.button("Open linked case", key=f"similar-open-case-{case_id}"):
                _open_alert_view(case_id, "Investigate")
            st.divider()
    elif view == "Graph":
        txn = app_state.get_transaction(alert.txn_id)
        if txn:
            st.write(
                {
                    "anchor_txn": txn.txn_id,
                    "account_id": txn.account_id,
                    "merchant_id": txn.merchant_id,
                    "device_id": txn.device_id,
                    "ip": txn.ip,
                    "amount": txn.amount,
                    "pattern_tag": txn.pattern_tag.value if txn.pattern_tag else "BASELINE",
                }
            )
            selected_txn_from_graph = _render_account_subgraph(app_state, account_id=txn.account_id, hops=2)
            if selected_txn_from_graph:
                selected_txn = app_state.get_transaction(selected_txn_from_graph)
                selected_customer = (
                    app_state.get_customer_by_account(selected_txn.account_id) if selected_txn else None
                )
                st.markdown("### Selected graph transaction")
                st.write(
                    {
                        "txn_id": selected_txn.txn_id if selected_txn else selected_txn_from_graph,
                        "user": selected_customer.name if selected_customer else None,
                        "account_id": selected_txn.account_id if selected_txn else None,
                        "merchant_id": selected_txn.merchant_id if selected_txn else None,
                        "amount": selected_txn.amount if selected_txn else None,
                        "channel": selected_txn.channel if selected_txn else None,
                        "txn_type": selected_txn.txn_type if selected_txn else None,
                    }
                )
                if st.button("Open selected transaction detail", key=f"open-selected-graph-txn-{selected_txn_from_graph}"):
                    _open_transaction_detail(selected_txn_from_graph)

            related = app_state.get_transactions_by_account(txn.account_id, limit=20)
            st.markdown("### Linked transactions")
            for item in related:
                st.caption(
                    f"{item.txn_id} | {item.ts} | ${item.amount:,.2f} | {item.channel}/{item.txn_type} | merchant={item.merchant_id}"
                )
                if st.button("Open detail", key=f"graph-related-open-{item.txn_id}"):
                    _open_transaction_detail(item.txn_id)
    else:
        st.code(SQL_OPEN_ALERTS, language="sql")


def _render_transaction_detail(app_state: AppState) -> None:
    st.subheader("Transaction detail")
    txn_id = st.session_state.get("selected_txn_id")
    if not txn_id:
        st.info("Select a transaction from dashboard, similar view, or graph.")
        return

    txn = app_state.get_transaction(txn_id)
    if txn is None:
        st.warning("Transaction not found.")
        return

    customer = app_state.get_customer_by_account(txn.account_id)
    case_id = app_state.get_case_id_by_txn(txn.txn_id)

    top_a, top_b, top_c = st.columns(3)
    top_a.metric("Transaction", txn.txn_id)
    top_b.metric("Amount", f"${txn.amount:,.2f}")
    top_c.metric("Linked case", case_id if case_id else "None")

    left, right = st.columns(2)
    left.write(
        {
            "account_id": txn.account_id,
            "counterparty_account_id": txn.counterparty_account_id,
            "merchant_id": txn.merchant_id,
            "channel": txn.channel,
            "txn_type": txn.txn_type,
            "device_id": txn.device_id,
            "ip": txn.ip,
            "geo": txn.geo,
            "pattern_tag": txn.pattern_tag.value if txn.pattern_tag else "BASELINE",
            "is_injected": txn.is_injected,
        }
    )
    right.write(
        {
            "customer_id": customer.customer_id if customer else None,
            "customer_name": customer.name if customer else None,
            "segment": customer.segment if customer else None,
            "risk_band": customer.risk_band if customer else None,
            "home_geo": customer.home_geo if customer else None,
        }
    )

    if case_id and st.button("Open linked case", key=f"txn-open-case-{case_id}"):
        _open_alert_view(case_id, "Investigate")

    with st.expander("Raw JSON"):
        st.json({"transaction": txn.model_dump(mode="json"), "customer": customer.model_dump(mode="json") if customer else None})


def _render_analyst_workbook() -> None:
    st.subheader("Analyst workbook")
    st.markdown("Open alerts by typology")
    st.code(SQL_OPEN_ALERTS, language="sql")
    st.download_button("Export SQL", data=SQL_OPEN_ALERTS, file_name="vw_open_alerts_by_typology.sql")


def _init_ui_state(app_state: AppState) -> None:
    if "screen_selector" not in st.session_state:
        st.session_state["screen_selector"] = "Admin dashboard"
    if "next_screen" not in st.session_state:
        st.session_state["next_screen"] = None
    if "selected_case_id" not in st.session_state:
        st.session_state["selected_case_id"] = None
    if "alert_view" not in st.session_state:
        st.session_state["alert_view"] = "Investigate"
    if "live_cursor" not in st.session_state:
        st.session_state["live_cursor"] = min(20, len(app_state.dataset.transactions))
    if "dashboard_filter" not in st.session_state:
        st.session_state["dashboard_filter"] = "ALL"
    if "selected_txn_id" not in st.session_state:
        st.session_state["selected_txn_id"] = None


def _open_alert_view(case_id: str, view: str) -> None:
    st.session_state["selected_case_id"] = case_id
    st.session_state["alert_view"] = view
    st.session_state["next_screen"] = "Alert detail"
    st.rerun()


def _open_transaction_detail(txn_id: str) -> None:
    st.session_state["selected_txn_id"] = txn_id
    st.session_state["next_screen"] = "Transaction detail"
    st.rerun()


@st.cache_resource
def _get_cached_state() -> AppState:
    return build_default_app_state(seed=42)


def _advance_live_cursor(app_state: AppState, tick_size: int) -> None:
    total = len(app_state.dataset.transactions)
    current = st.session_state.get("live_cursor", 0)
    if current < total:
        st.session_state["live_cursor"] = min(total, current + tick_size)


def _render_live_mindmap(transactions: list[Transaction]) -> None:
    nodes_by_id: dict[str, Node] = {}
    edges: list[Edge] = []

    for txn in transactions:
        account_node = _add_node(nodes_by_id, f"account:{txn.account_id}", txn.account_id, "#5A67D8", f"Account {txn.account_id}")
        merchant_node = _add_node(nodes_by_id, f"merchant:{txn.merchant_id}", txn.merchant_id, "#2B6CB0", f"Merchant {txn.merchant_id}")
        device_node = _add_node(nodes_by_id, f"device:{txn.device_id}", txn.device_id, "#2F855A", f"Device {txn.device_id}")
        ip_node = _add_node(nodes_by_id, f"ip:{txn.ip}", txn.ip, "#B7791F", f"IP {txn.ip}")

        edges.append(Edge(source=account_node.id, target=merchant_node.id, label="PAID_AT"))
        edges.append(Edge(source=account_node.id, target=device_node.id, label="USES_DEVICE"))
        edges.append(Edge(source=device_node.id, target=ip_node.id, label="SEEN_ON_IP"))

        if txn.counterparty_account_id:
            cp_node = _add_node(
                nodes_by_id,
                f"account:{txn.counterparty_account_id}",
                txn.counterparty_account_id,
                "#5A67D8",
                f"Account {txn.counterparty_account_id}",
            )
            edges.append(Edge(source=account_node.id, target=cp_node.id, label="SENT_TO"))

    config = Config(
        width="100%",
        height=520,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        collapsible=True,
    )
    agraph(nodes=list(nodes_by_id.values()), edges=edges, config=config)


def _render_account_subgraph(app_state: AppState, account_id: str, hops: int) -> str | None:
    neighborhood = app_state.graph.neighborhood(account_id=account_id, hops=hops)
    selected_nodes = set(neighborhood)
    nodes_by_id: dict[str, Node] = {}
    edges: list[Edge] = []

    related_transactions = app_state.get_transactions_by_account(account_id=account_id, limit=50)
    for txn in related_transactions:
        txn_node_id = f"txn:{txn.txn_id}"
        txn_title = (
            f"txn={txn.txn_id}\namount={txn.amount}\nchannel={txn.channel}\n"
            f"type={txn.txn_type}\nmerchant={txn.merchant_id}\nip={txn.ip}"
        )
        txn_node = _add_node(nodes_by_id, txn_node_id, txn.txn_id, "#D53F8C", txn_title)
        account_node = _add_node(nodes_by_id, f"account:{txn.account_id}", txn.account_id, _node_color("account"), f"account: {txn.account_id}")
        merchant_node = _add_node(nodes_by_id, f"merchant:{txn.merchant_id}", txn.merchant_id, _node_color("merchant"), f"merchant: {txn.merchant_id}")
        device_node = _add_node(nodes_by_id, f"device:{txn.device_id}", txn.device_id, _node_color("device"), f"device: {txn.device_id}")
        ip_node = _add_node(nodes_by_id, f"ip:{txn.ip}", txn.ip, _node_color("ip"), f"ip: {txn.ip}")
        edges.append(Edge(source=account_node.id, target=txn_node.id, label="HAS_TXN", title=f"txn={txn.txn_id}"))
        edges.append(Edge(source=txn_node.id, target=merchant_node.id, label="PAID_AT", title=f"txn={txn.txn_id}"))
        edges.append(Edge(source=txn_node.id, target=device_node.id, label="USED_DEVICE", title=f"txn={txn.txn_id}"))
        edges.append(Edge(source=device_node.id, target=ip_node.id, label="SEEN_ON_IP", title=f"txn={txn.txn_id}"))

    for source, target, data in app_state.graph.graph.edges(data=True):
        if source not in selected_nodes or target not in selected_nodes:
            continue
        source_type, source_value = source.split(":", maxsplit=1)
        target_type, target_value = target.split(":", maxsplit=1)

        source_node = _add_node(nodes_by_id, source, source_value, _node_color(source_type), f"{source_type}: {source_value}")
        target_node = _add_node(nodes_by_id, target, target_value, _node_color(target_type), f"{target_type}: {target_value}")

        edge_label = str(data.get("label", "LINK"))
        txn_id = str(data.get("txn_id", ""))
        edges.append(Edge(source=source_node.id, target=target_node.id, label=edge_label, title=f"txn={txn_id}"))

    config = Config(
        width="100%",
        height=520,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        collapsible=True,
    )
    selected = agraph(nodes=list(nodes_by_id.values()), edges=edges, config=config)
    if isinstance(selected, str) and selected.startswith("txn:"):
        return selected.split(":", maxsplit=1)[1]
    return None


def _add_node(nodes: dict[str, Node], node_id: str, label: str, color: str, title: str) -> Node:
    if node_id in nodes:
        return nodes[node_id]
    node = Node(id=node_id, label=label, color=color, title=title, size=20)
    nodes[node_id] = node
    return node


def _node_color(node_type: str) -> str:
    colors = {
        "account": "#5A67D8",
        "merchant": "#2B6CB0",
        "device": "#2F855A",
        "ip": "#B7791F",
    }
    return colors.get(node_type, "#718096")


def _filter_transactions(transactions: list[Transaction], dashboard_filter: str, alert_txn_ids: set[str]) -> list[Transaction]:
    if dashboard_filter == "ALL":
        return transactions
    if dashboard_filter == "BASELINE":
        return [txn for txn in transactions if txn.txn_id not in alert_txn_ids]
    if dashboard_filter == "ALERTS":
        return [txn for txn in transactions if txn.txn_id in alert_txn_ids]
    return [txn for txn in transactions if (txn.pattern_tag.value if txn.pattern_tag else "BASELINE") == dashboard_filter]


if __name__ == "__main__":
    main()
