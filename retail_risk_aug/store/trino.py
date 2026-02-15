from __future__ import annotations

from typing import Any


class TrinoClient:
    def __init__(
        self,
        host: str,
        port: int,
        catalog: str,
        schema: str,
        user: str = "risk-user",
        http_scheme: str = "http",
    ) -> None:
        self.host = host
        self.port = port
        self.catalog = catalog
        self.schema = schema
        self.user = user
        self.http_scheme = http_scheme
        self._connection: Any | None = None

    def connect(self) -> None:
        try:
            import trino
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("trino package is required for TrinoClient") from exc

        self._connection = trino.dbapi.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            catalog=self.catalog,
            schema=self.schema,
            http_scheme=self.http_scheme,
        )

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def execute(self, query: str) -> list[dict[str, object]]:
        connection = self._require_connection()
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in rows]

    def _require_connection(self) -> Any:
        if self._connection is None:
            raise RuntimeError("TrinoClient is not connected. Call connect() first.")
        return self._connection
