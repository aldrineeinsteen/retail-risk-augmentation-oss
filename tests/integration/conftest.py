from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: marks tests requiring external services")


def require_integration_enabled() -> None:
    if os.getenv("RUN_INTEGRATION", "0") != "1":
        pytest.skip("Integration tests are disabled. Set RUN_INTEGRATION=1 to run.")


@pytest.fixture
def integration_enabled() -> None:
    require_integration_enabled()
