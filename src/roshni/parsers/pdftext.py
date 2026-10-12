"""Canonical PDF text: poppler `pdftotext -layout`.

Uses a local poppler if available (Docker image, CI, Linux); otherwise runs the project Docker
image `roshni:dev`. xpdf's pdftotext (bundled with Git for Windows) is rejected because its layout
output differs from poppler's. Results are cached by SHA-256 under data/cache/pdftext/.
"""

import functools
import os
import shutil
import subprocess
from pathlib import Path

from roshni.paths import DATA_DIR
from roshni.sources.inventory import sha256_of

DOCKER_IMAGE = os.environ.get("ROSHNI_DOCKER_IMAGE", "roshni:dev")
CACHE_DIR = DATA_DIR / "cache" / "pdftext"


class PdfTextUnavailable(RuntimeError):
    pass


@functools.cache
def _local_poppler() -> str | None:
    # ROSHNI_PDFTEXT=docker forces the project image (the daily job: a runner's own poppler
    # may be a different version from the canonical one).
    if os.environ.get("ROSHNI_PDFTEXT") == "docker":
        return None
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    out = subprocess.run([exe, "-v"], capture_output=True, text=True)
    banner = (out.stdout + out.stderr).lower()
    return exe if "poppler" in banner else None


def poppler_version() -> str:
    exe = _local_poppler()
    cmd = [exe, "-v"] if exe else _docker_cmd(Path.cwd(), "-v")
    out = subprocess.run(cmd, capture_output=True, text=True)
    return (out.stdout + out.stderr).splitlines()[0].strip()


def _docker_cmd(folder: Path, *args: str) -> list[str]:
    if not shutil.which("docker"):
        raise PdfTextUnavailable("no poppler pdftotext and no docker; build the image first")
    return [
        "docker", "run", "--rm", "-v", f"{folder.resolve()}:/in:ro",
        "--entrypoint", "pdftotext", DOCKER_IMAGE, *args,
    ]  # fmt: skip


def _extract(pdf: Path, first: int | None, last: int | None) -> str:
    pages = [*(["-f", str(first)] if first else []), *(["-l", str(last)] if last else [])]
    exe = _local_poppler()
    if exe:
        cmd = [exe, "-layout", "-enc", "UTF-8", *pages, str(pdf), "-"]
    else:
        cmd = _docker_cmd(pdf.parent, "-layout", "-enc", "UTF-8", *pages, f"/in/{pdf.name}", "-")
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode != 0:
        raise PdfTextUnavailable(out.stderr.decode(errors="replace")[:500])
    return out.stdout.decode("utf-8")


def pdf_text(pdf: Path, first: int | None = None, last: int | None = None) -> str:
    """Layout text of a PDF (optionally a page range). Pages are separated by form feeds."""
    key = sha256_of(pdf) + (f"_p{first or 1}-{last or 'end'}" if first or last else "")
    cached = CACHE_DIR / f"{key}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    text = _extract(pdf, first, last)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(text, encoding="utf-8", newline="\n")
    return text
