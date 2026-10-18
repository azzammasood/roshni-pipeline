"""Rules for hand-recorded IESCO social-media notices (dbt/seeds/iesco_social_notices.csv).

Nothing in that file is collected automatically (facebook.com forbids it): a person reads a post
and records it. These checks keep every row linkable, dated and in our own words.
"""

import csv
import re
from datetime import date
from urllib.parse import urlsplit

from roshni.paths import REPO_ROOT

SEED = REPO_ROOT / "dbt" / "seeds" / "iesco_social_notices.csv"
COLUMNS = [
    "notice_id", "platform", "posted_on", "url", "kind", "circle", "areas", "window_date",
    "start_local", "end_local", "summary", "added_by", "added_on",
]  # fmt: skip
KINDS = {"maintenance", "load_shedding", "restoration", "other"}
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$|^24:00$")


def rows() -> list[dict[str, str]]:
    with SEED.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == COLUMNS
        return list(reader)


def test_header_is_fixed() -> None:
    rows()


def test_every_notice_follows_the_rules() -> None:
    ids = set()
    for r in rows():
        where = r["notice_id"] or "(no id)"
        assert r["notice_id"] and r["notice_id"] not in ids, f"{where}: missing or repeated id"
        ids.add(r["notice_id"])
        assert r["platform"] == "facebook", where
        host = urlsplit(r["url"]).netloc.lower()
        assert host.endswith("facebook.com") or host == "fb.watch", f"{where}: link is not a post"
        assert r["kind"] in KINDS, where
        posted = date.fromisoformat(r["posted_on"])
        assert date.fromisoformat(r["added_on"]) >= posted, f"{where}: added before it was posted"
        if r["window_date"]:
            date.fromisoformat(r["window_date"])
        for t in ("start_local", "end_local"):
            assert not r[t] or HHMM.match(r[t]), f"{where}: {t} must be HH:MM"
        # Our own words, kept short: a summary, never the post copied out.
        assert 0 < len(r["summary"]) <= 280, f"{where}: summary must be 1-280 characters"
        assert r["added_by"], where
