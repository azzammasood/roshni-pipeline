"""Parser test helpers: feed synthetic layout text instead of running poppler."""

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def fake_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str, str], Path]:
    """Create a dummy PDF whose `pdf_text` is the given string (pages split by form feed)."""
    texts: dict[str, str] = {}

    def fake_pdf_text(path: Path, first=None, last=None) -> str:
        return texts[Path(path).name]

    for mod in ("iesco_press", "kelectric", "pbs_urban", "pbs_rural"):
        monkeypatch.setattr(f"roshni.parsers.{mod}.pdf_text", fake_pdf_text)

    def make(name: str, text: str) -> Path:
        p = tmp_path / name
        p.write_bytes(b"%PDF-1.4 synthetic " + name.encode())
        texts[name] = text
        return p

    return make
