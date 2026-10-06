"""Shared pytest config: skip tests needing data-sources/ when it is absent (e.g. in CI)."""

import pytest

from roshni.paths import DATA_SOURCES_DIR


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if DATA_SOURCES_DIR.is_dir():
        return
    skip = pytest.mark.skip(reason=f"data-sources/ not found at {DATA_SOURCES_DIR}")
    for item in items:
        if "needs_data_sources" in item.keywords:
            item.add_marker(skip)
