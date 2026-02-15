from __future__ import annotations

import pytest


@pytest.mark.integration
def test_iceberg_store_write_scaffold(integration_enabled: None) -> None:
    pytest.importorskip("pyiceberg")
    pytest.skip(
        "Scaffold only: wire this test with MinIO + Iceberg catalog fixture (nessie/jdbc/hms) in Phase 2.1/2.2."
    )
