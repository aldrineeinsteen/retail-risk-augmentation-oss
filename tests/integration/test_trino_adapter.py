from __future__ import annotations

import pytest


@pytest.mark.integration
def test_trino_execute_query_scaffold(integration_enabled: None) -> None:
    pytest.importorskip("trino")
    pytest.skip("Scaffold only: wire this test with Trino container fixture in Phase 2.1/2.2.")
