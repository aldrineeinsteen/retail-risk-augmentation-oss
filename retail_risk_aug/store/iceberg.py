from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from retail_risk_aug.models import Transaction


@dataclass(slots=True)
class EmbeddingRecord:
    embedding_id: str
    entity_type: str
    entity_id: str
    vector: list[float]
    model_version: str
    created_ts: datetime


class IcebergStore:
    def __init__(
        self,
        catalog_type: str,
        warehouse: str,
        access_key: str,
        secret_key: str,
        endpoint: str,
        catalog_name: str = "default",
        namespace: str = "risk",
    ) -> None:
        self.catalog_type = catalog_type
        self.warehouse = warehouse
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint = endpoint
        self.catalog_name = catalog_name
        self.namespace = namespace
        self._catalog: Any | None = None

    def connect(self) -> None:
        try:
            from pyiceberg.catalog import load_catalog
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("pyiceberg is required for IcebergStore") from exc

        self._catalog = load_catalog(
            self.catalog_name,
            **self._catalog_properties(),
        )

    def write_curated_transactions(self, transactions: list[Transaction]) -> int:
        table = self._load_or_create_transactions_table()
        rows = []
        for txn in transactions:
            rows.append(
                {
                    "txn_id": txn.txn_id,
                    "ts": txn.ts,
                    "account_id": txn.account_id,
                    "counterparty_account_id": txn.counterparty_account_id,
                    "merchant_id": txn.merchant_id,
                    "amount": txn.amount,
                    "currency": txn.currency,
                    "channel": txn.channel,
                    "txn_type": txn.txn_type,
                    "device_id": txn.device_id,
                    "ip": txn.ip,
                    "geo": txn.geo,
                    "narrative": txn.narrative,
                    "is_injected": txn.is_injected,
                    "pattern_tag": txn.pattern_tag.value if txn.pattern_tag else None,
                    "injection_group_id": txn.injection_group_id,
                }
            )

        self._append_rows(table=table, rows=rows)
        return len(rows)

    def write_embeddings(self, embeddings: list[EmbeddingRecord]) -> int:
        table = self._load_or_create_embeddings_table()
        rows = [asdict(record) for record in embeddings]
        self._append_rows(table=table, rows=rows)
        return len(rows)

    def _catalog_properties(self) -> dict[str, str]:
        if self.catalog_type not in {"nessie", "jdbc", "hms"}:
            raise ValueError("catalog_type must be one of: nessie, jdbc, hms")
        return {
            "type": self.catalog_type,
            "warehouse": self.warehouse,
            "s3.endpoint": self.endpoint,
            "s3.access-key-id": self.access_key,
            "s3.secret-access-key": self.secret_key,
            "s3.path-style-access": "true",
            "s3.region": "us-east-1",
        }

    def _load_or_create_transactions_table(self) -> Any:
        try:
            from pyiceberg.schema import NestedField, Schema
            from pyiceberg.types import BooleanType, DoubleType, StringType, TimestampType
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("pyiceberg is required for IcebergStore") from exc

        catalog = self._require_catalog()
        identifier = (self.namespace, "curated_transactions")
        schema = Schema(
            NestedField(1, "txn_id", StringType(), required=True),
            NestedField(2, "ts", TimestampType(), required=True),
            NestedField(3, "account_id", StringType(), required=True),
            NestedField(4, "counterparty_account_id", StringType(), required=False),
            NestedField(5, "merchant_id", StringType(), required=True),
            NestedField(6, "amount", DoubleType(), required=True),
            NestedField(7, "currency", StringType(), required=True),
            NestedField(8, "channel", StringType(), required=True),
            NestedField(9, "txn_type", StringType(), required=True),
            NestedField(10, "device_id", StringType(), required=True),
            NestedField(11, "ip", StringType(), required=True),
            NestedField(12, "geo", StringType(), required=True),
            NestedField(13, "narrative", StringType(), required=True),
            NestedField(14, "is_injected", BooleanType(), required=True),
            NestedField(15, "pattern_tag", StringType(), required=False),
            NestedField(16, "injection_group_id", StringType(), required=False),
        )
        return self._load_or_create_table(catalog=catalog, identifier=identifier, schema=schema)

    def _load_or_create_embeddings_table(self) -> Any:
        try:
            from pyiceberg.schema import NestedField, Schema
            from pyiceberg.types import DoubleType, ListType, StringType, TimestampType
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("pyiceberg is required for IcebergStore") from exc

        catalog = self._require_catalog()
        identifier = (self.namespace, "embeddings")
        schema = Schema(
            NestedField(1, "embedding_id", StringType(), required=True),
            NestedField(2, "entity_type", StringType(), required=True),
            NestedField(3, "entity_id", StringType(), required=True),
            NestedField(4, "vector", ListType(element_id=5, element_type=DoubleType(), element_required=True), required=True),
            NestedField(6, "model_version", StringType(), required=True),
            NestedField(7, "created_ts", TimestampType(), required=True),
        )
        return self._load_or_create_table(catalog=catalog, identifier=identifier, schema=schema)

    def _load_or_create_table(self, catalog: Any, identifier: tuple[str, str], schema: Any) -> Any:
        try:
            return catalog.load_table(identifier)
        except Exception:
            try:
                catalog.create_namespace((self.namespace,))
            except Exception:
                pass
            return catalog.create_table(identifier=identifier, schema=schema)

    def _append_rows(self, table: Any, rows: list[dict[str, Any]]) -> None:
        try:
            import pyarrow as pa
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("pyarrow is required for Iceberg append operations") from exc

        arrow_table = pa.Table.from_pylist(rows)
        table.append(arrow_table)

    def _require_catalog(self) -> Any:
        if self._catalog is None:
            raise RuntimeError("IcebergStore is not connected. Call connect() first.")
        return self._catalog


def make_embedding_record(
    embedding_id: str,
    entity_type: str,
    entity_id: str,
    vector: list[float],
    model_version: str,
) -> EmbeddingRecord:
    return EmbeddingRecord(
        embedding_id=embedding_id,
        entity_type=entity_type,
        entity_id=entity_id,
        vector=vector,
        model_version=model_version,
        created_ts=datetime.now(tz=UTC),
    )
