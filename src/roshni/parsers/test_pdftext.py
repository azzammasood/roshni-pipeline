"""Canonical PDF text: xpdf is refused, and text is cached by the file's SHA-256, not its name."""

import subprocess
from pathlib import Path

import pytest

from roshni.parsers import pdftext


def fake_run(banner: str, calls: list[list[str]]):
    def run(cmd, capture_output=True, text=False):
        calls.append(cmd)
        out = banner if "-v" in cmd else "page one\fpage two"
        return subprocess.CompletedProcess(
            cmd, 0, out if text else out.encode(), "" if text else b""
        )

    return run


@pytest.mark.parametrize(
    "banner,local",
    [
        ("pdftotext version 25.03.0\nCopyright 2005-2025 The Poppler Developers", True),
        ("pdftotext version 4.00\nCopyright 1996-2017 Glyph & Cog, LLC", False),  # xpdf
    ],
)
def test_only_poppler_is_used_locally(monkeypatch, banner: str, local: bool) -> None:
    pdftext._local_poppler.cache_clear()
    monkeypatch.delenv("ROSHNI_PDFTEXT", raising=False)
    monkeypatch.setattr(pdftext.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(pdftext.subprocess, "run", fake_run(banner, []))
    try:
        assert (pdftext._local_poppler() is not None) is local
    finally:
        pdftext._local_poppler.cache_clear()


def test_cache_is_keyed_by_content(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(pdftext, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(pdftext, "_local_poppler", lambda: "/bin/pdftotext")
    monkeypatch.setattr(pdftext.subprocess, "run", fake_run("", calls))
    one = tmp_path / "LSM-Oct.pdf"
    one.write_bytes(b"%PDF-1.4 same bytes")
    renamed = tmp_path / "copy-under-another-name.pdf"
    renamed.write_bytes(one.read_bytes())

    assert pdftext.pdf_text(one) == "page one\fpage two"
    assert pdftext.pdf_text(renamed) == "page one\fpage two"
    assert len(calls) == 1  # same bytes, other name: served from the cache

    pdftext.pdf_text(one, first=1, last=1)
    assert len(calls) == 2  # a page range is its own cache entry

    one.write_bytes(b"%PDF-1.4 republished in place")  # same name, new bytes
    pdftext.pdf_text(one)
    assert len(calls) == 3
