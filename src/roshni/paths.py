"""Repository paths. Always use pathlib; never hardcode separators."""

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("ROSHNI_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = REPO_ROOT / "data"
DATA_SOURCES_DIR = REPO_ROOT / "data-sources"
CONFIG_DIR = REPO_ROOT / "config"
