from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from retail_risk_aug.models import Alert, Transaction

try:
    from cassandra.cluster import Cluster, Session
    from cassandra.query import BatchStatement
except Exception:  # pragma: no cover
    Cluster = None
    Session = None
    BatchStatement = None


class CassandraStore:
    def __init__(
        self,
        contact_points: list[str],
        username: str,
        password: str,
        keyspace: str = "retail_risk",
        port: int = 9042,
    ) -> None:
        self.contact_points = contact_points
        self.username = username
        self.password = password
        self.keyspace = keyspace
        self.port = port
        self._cluster: Cluster | None = None
        self._session: Session | None = None

    def connect(self) -> None:
        if Cluster is None:
            raise RuntimeError("cassandra-driver is required for CassandraStore")

        auth_provider = None
        if self.username and self.password:
            from cassandra.auth import PlainTextAuthProvider

            auth_provider = PlainTextAuthProvider(username=self.username, password=self.password)

        self._cluster = Cluster(contact_points=self.contact_points, port=self.port, auth_provider=auth_provider)
        self._session = self._cluster.connect()

    def close(self) -> None:
        if self._session is not None:
            self._session.shutdown()
        if self._cluster is not None:
            self._cluster.shutdown()
        self._session = None
        self._cluster = None

    def create_schema(self) -> None:
        session = self._require_session()
        session.execute(
            f"""
            CREATE KEYSPACE IF NOT EXISTS {self.keyspace}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
            """
        )
        session.set_keyspace(self.keyspace)

        session.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions_by_account (
                account_id text,
                ts timestamp,
                txn_id text,
                counterparty_account_id text,
                merchant_id text,
                amount double,
                currency text,
                channel text,
                txn_type text,
                device_id text,
                ip text,
                geo text,
                narrative text,
                is_injected boolean,
                pattern_tag text,
                injection_group_id text,
                PRIMARY KEY ((account_id), ts, txn_id)
            ) WITH CLUSTERING ORDER BY (ts DESC, txn_id ASC)
            """
        )

        session.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions_by_merchant (
                merchant_id text,
                ts timestamp,
                txn_id text,
                account_id text,
                amount double,
                channel text,
                txn_type text,
                is_injected boolean,
                pattern_tag text,
                PRIMARY KEY ((merchant_id), ts, txn_id)
            ) WITH CLUSTERING ORDER BY (ts DESC, txn_id ASC)
            """
        )

        session.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts_by_status (
                status text,
                created_ts timestamp,
                case_id text,
                txn_id text,
                score double,
                reason_codes list<text>,
                resolution text,
                resolution_ts timestamp,
                PRIMARY KEY ((status), created_ts, case_id)
            ) WITH CLUSTERING ORDER BY (created_ts DESC, case_id ASC)
            """
        )

    def write_transactions(self, transactions: list[Transaction]) -> None:
        session = self._require_session()
        session.set_keyspace(self.keyspace)
        account_stmt = session.prepare(
            """
            INSERT INTO transactions_by_account (
                account_id, ts, txn_id, counterparty_account_id, merchant_id,
                amount, currency, channel, txn_type, device_id, ip, geo,
                narrative, is_injected, pattern_tag, injection_group_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        merchant_stmt = session.prepare(
            """
            INSERT INTO transactions_by_merchant (
                merchant_id, ts, txn_id, account_id, amount, channel, txn_type,
                is_injected, pattern_tag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )

        for txn in transactions:
            session.execute(
                account_stmt,
                (
                    txn.account_id,
                    txn.ts,
                    txn.txn_id,
                    txn.counterparty_account_id,
                    txn.merchant_id,
                    txn.amount,
                    txn.currency,
                    txn.channel,
                    txn.txn_type,
                    txn.device_id,
                    txn.ip,
                    txn.geo,
                    txn.narrative,
                    txn.is_injected,
                    txn.pattern_tag.value if txn.pattern_tag else None,
                    txn.injection_group_id,
                ),
            )
            session.execute(
                merchant_stmt,
                (
                    txn.merchant_id,
                    txn.ts,
                    txn.txn_id,
                    txn.account_id,
                    txn.amount,
                    txn.channel,
                    txn.txn_type,
                    txn.is_injected,
                    txn.pattern_tag.value if txn.pattern_tag else None,
                ),
            )

    def write_alerts(self, alerts: list[Alert]) -> None:
        session = self._require_session()
        session.set_keyspace(self.keyspace)
        stmt = session.prepare(
            """
            INSERT INTO alerts_by_status (
                status, created_ts, case_id, txn_id, score, reason_codes,
                resolution, resolution_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        for alert in alerts:
            session.execute(
                stmt,
                (
                    alert.status,
                    alert.created_ts,
                    alert.case_id,
                    alert.txn_id,
                    alert.score,
                    alert.reason_codes,
                    alert.resolution,
                    alert.resolution_ts,
                ),
            )

    def read_transactions_by_account(self, account_id: str, limit: int = 100) -> list[dict[str, object]]:
        session = self._require_session()
        session.set_keyspace(self.keyspace)
        rows = session.execute(
            """
            SELECT account_id, ts, txn_id, counterparty_account_id, merchant_id,
                   amount, currency, channel, txn_type, device_id, ip, geo,
                   narrative, is_injected, pattern_tag, injection_group_id
            FROM transactions_by_account
            WHERE account_id = %s
            LIMIT %s
            """,
            (account_id, limit),
        )
        return [dict(row._asdict()) for row in rows]

    @classmethod
    def from_env(
        cls,
        contact_points: str,
        username: str,
        password: str,
        keyspace: str = "retail_risk",
        port: int = 9042,
    ) -> CassandraStore:
        cp_list = [item.strip() for item in contact_points.split(",") if item.strip()]
        return cls(contact_points=cp_list, username=username, password=password, keyspace=keyspace, port=port)

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("CassandraStore is not connected. Call connect() first.")
        return self._session


def make_alert_from_score(txn_id: str, score: float, reason_codes: list[str]) -> Alert:
    return Alert(
        case_id=f"CASE-{uuid4().hex[:10]}",
        txn_id=txn_id,
        score=max(0.0, min(1.0, score)),
        reason_codes=reason_codes,
        created_ts=datetime.now(tz=UTC),
    )
