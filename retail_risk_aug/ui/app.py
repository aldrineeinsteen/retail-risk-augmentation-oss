from __future__ import annotations

import streamlit as st

from retail_risk_aug.app_state import AppState, build_default_app_state


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
    state = build_default_app_state(seed=42)

    screen = st.sidebar.selectbox(
        "Screen",
        ["Admin dashboard", "Alerts list", "Alert detail", "Analyst workbook"],
    )

    if screen == "Admin dashboard":
        _render_admin_dashboard(state)
    elif screen == "Alerts list":
        _render_alerts_list(state)
    elif screen == "Alert detail":
        _render_alert_detail(state)
    else:
        _render_analyst_workbook()


def _render_admin_dashboard(app_state: AppState) -> None:
    st.subheader("Admin dashboard")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Transactions", len(app_state.dataset.transactions))
    col_b.metric("Open alerts", len(app_state.list_alerts(status="open")))
    col_c.metric("Model version", "v1")
    col_d.metric("Last job run", "local-now")


def _render_alerts_list(app_state: AppState) -> None:
    st.subheader("Alerts list")
    alerts = app_state.list_alerts(status="open")
    for alert in alerts[:50]:
        st.markdown(
            f"**{alert.case_id}** | txn={alert.txn_id} | score={alert.score:.2f} | reasons={', '.join(alert.reason_codes)}"
        )
        st.markdown(
            " | ".join(
                [
                    f"[Investigate](?screen=Alert+detail&case_id={alert.case_id})",
                    f"[Similar](?screen=Alert+detail&case_id={alert.case_id}#similar)",
                    f"[Graph](?screen=Alert+detail&case_id={alert.case_id}#graph)",
                    "[SQL](?screen=Analyst+workbook)",
                ]
            )
        )


def _render_alert_detail(app_state: AppState) -> None:
    st.subheader("Alert detail")
    alerts = app_state.list_alerts(status="open")
    alert_ids = [alert.case_id for alert in alerts]
    if not alert_ids:
        st.info("No open alerts.")
        return

    selected_case = st.selectbox("Case", alert_ids)
    alert = app_state.get_alert(selected_case)
    if alert is None:
        st.warning("Alert not found.")
        return

    st.write({
        "case_id": alert.case_id,
        "txn_id": alert.txn_id,
        "score": alert.score,
        "reason_codes": alert.reason_codes,
    })

    st.markdown("### Similar")
    similar = app_state.get_similar_transactions(alert.txn_id, k=10)
    st.write([item.model_dump(mode="json") for item in similar])

    st.markdown("### Graph")
    txn = app_state.get_transaction(alert.txn_id)
    if txn:
        neighborhood = app_state.graph.neighborhood(txn.account_id, hops=2)
        st.write({"account_id": txn.account_id, "neighborhood": neighborhood})

    st.markdown("### SQL")
    st.code(SQL_OPEN_ALERTS, language="sql")


def _render_analyst_workbook() -> None:
    st.subheader("Analyst workbook")
    st.markdown("Open alerts by typology")
    st.code(SQL_OPEN_ALERTS, language="sql")
    st.download_button("Export SQL", data=SQL_OPEN_ALERTS, file_name="vw_open_alerts_by_typology.sql")


if __name__ == "__main__":
    main()
