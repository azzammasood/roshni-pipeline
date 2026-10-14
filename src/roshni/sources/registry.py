"""Typed view of config/sources.yml."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from roshni.paths import CONFIG_DIR

Discovery = Literal[
    "iesco_xlsx_table",
    "iesco_press_release_tab",
    "fixed_url",
    "listing_pdf_pattern",
    "listing_pdfs",
]


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discovery: Discovery
    listing_url: str | None = None
    url: str | None = None
    circles: dict[str, str] | None = None
    tab_id: str | None = None
    language: str | None = None
    refetch: bool = True
    listing_link_pattern: str | None = None
    link_pattern: str | None = None
    exclude_pattern: str | None = None
    # Reduce the fetched file before storing it (news feeds: load-shedding headlines only).
    trim: Literal["news_headlines"] | None = None
    # Links the publisher lists but that return 404/410 (recorded in data-audit.md): logged as a
    # known gap, not a run failure. Still requested every run, so a fixed link is picked up.
    known_broken: list[str] = []


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_agent: str
    min_request_interval_seconds: float = 1.0
    timeout_seconds: float = 90
    sources: dict[str, SourceConfig]


def load_registry(path: Path | None = None) -> Registry:
    path = path or CONFIG_DIR / "sources.yml"
    with path.open(encoding="utf-8") as f:
        return Registry.model_validate(yaml.safe_load(f))
