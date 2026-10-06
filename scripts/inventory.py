"""Print a Markdown inventory table of data-sources/ (name, bytes, SHA-256).

Usage: uv run python scripts/inventory.py
"""

import sys

from roshni.paths import DATA_SOURCES_DIR
from roshni.sources.inventory import inventory


def main() -> int:
    entries, missing = inventory(DATA_SOURCES_DIR)
    print("| File | Bytes | SHA-256 |")
    print("|---|---:|---|")
    for e in entries:
        print(f"| `{e.name}` | {e.bytes:,} | `{e.sha256}` |")
    if missing:
        print("\nMissing: " + ", ".join(missing), file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
