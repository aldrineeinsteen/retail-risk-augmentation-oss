from __future__ import annotations

import pytest


@pytest.mark.integration
def test_cassandra_store_schema_and_roundtrip_scaffold(integration_enabled: None) -> None:
    pytest.importorskip("cassandra")
    pytest.skip(
        "Scaffold only: wire this test with testcontainers Cassandra in Phase 2.1/2.2 when infra profile is enabled."
    )
