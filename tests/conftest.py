"""Shared fixtures for the GloBird tests.

Test modules stub ``homeassistant`` in ``sys.modules`` themselves, so this file
imports neither Home Assistant nor the integration.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from .fixtures.deprecations import HANDLER as DEPRECATION_REPORTS


@pytest.fixture(autouse=True)
def fail_on_ha_deprecation_reports() -> Generator[None]:
    """Fail when Home Assistant logs deprecated use by this integration.

    Reports logged while modules were imported surface on the first test.
    """
    yield
    if reports := DEPRECATION_REPORTS.pop_reports():
        pytest.fail(
            "Home Assistant reported deprecated use by globird:\n" + "\n".join(reports),
            pytrace=False,
        )
