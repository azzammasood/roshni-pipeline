"""End-to-end snapshot runs against a mocked site."""

from pathlib import Path

import httpx

from roshni.fetch.http import PoliteClient
from roshni.fetch.snapshot import run_snapshot
from roshni.fetch.store import SnapshotStore
from roshni.sources.registry import Registry, SourceConfig

LISTING = "https://ke.com.pk/load-shed-schedule/"
SCHED = "https://ke.com.pk/wp-content/uploads/2026/08/LSM-Aug.pdf"
PR_LISTING = "https://iesco.com.pk/press-release"


class FakeSite:
    """Serves a K-Electric-like page with ETag support and an IESCO press-release tab."""

    def __init__(self) -> None:
        self.files = {SCHED: (b"%PDF schedule v1", '"e1"'), PR_LISTING + "/A.pdf": (b"%PDF A", "")}
        self.links = [SCHED]
        self.requests: list[str] = []

    def handler(self, req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        self.requests.append(url)
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /wp-admin/\n")
        if url == LISTING:
            return httpx.Response(
                200, text="".join(f'<a href="{u}">Download</a>' for u in self.links)
            )
        if url == PR_LISTING:
            return httpx.Response(
                200,
                text='<div id="power-desktop"><table><tr><td>Shutdown 6 Oct</td>'
                '<td><a href="/press-release/A.pdf">English</a></td></tr></table></div>',
            )
        if url in self.files:
            body, etag = self.files[url]
            if etag and req.headers.get("if-none-match") == etag:
                return httpx.Response(304, headers={"etag": etag})
            headers = {"etag": etag} if etag else {}
            return httpx.Response(200, content=body, headers=headers)
        return httpx.Response(404)


REG = Registry(
    user_agent="roshni-pipeline/0.1 (+test)",
    min_request_interval_seconds=0,
    sources={
        "kelectric_schedule": SourceConfig(
            discovery="listing_pdf_pattern", listing_url=LISTING, link_pattern="(?i)lsm"
        ),
        "iesco_press_release": SourceConfig(
            discovery="iesco_press_release_tab",
            listing_url=PR_LISTING,
            tab_id="power-desktop",
            language="English",
            refetch=False,
        ),
    },
)


def run(site: FakeSite, root: Path):
    with PoliteClient(REG.user_agent, 0, transport=httpx.MockTransport(site.handler)) as c:
        return run_snapshot(c, SnapshotStore(root), REG)


def test_first_run_new_second_run_unchanged(tmp_path: Path) -> None:
    site = FakeSite()
    r1 = run(site, tmp_path)
    assert r1.ok and r1.count("new") == 2
    store = SnapshotStore(tmp_path)
    rec = store.last_good("kelectric_schedule", "schedule")
    assert rec and rec.changed and rec.etag == '"e1"' and rec.bytes == 16
    assert (tmp_path / rec.path).read_bytes() == b"%PDF schedule v1"

    site.requests.clear()
    r2 = run(site, tmp_path)
    assert r2.ok
    assert r2.count("unchanged") == 1 and r2.count("known") == 1 and r2.count("new") == 0
    assert PR_LISTING + "/A.pdf" not in site.requests  # press releases are not re-fetched
    last = SnapshotStore(tmp_path).records[-1]
    assert last.http_status == 304 and not last.changed and last.sha256 == rec.sha256


def test_content_change_stores_new_file(tmp_path: Path) -> None:
    site = FakeSite()
    run(site, tmp_path)
    site.files[SCHED] = (b"%PDF schedule v2", '"e2"')
    r = run(site, tmp_path)
    assert r.count("changed") == 1
    files = list((tmp_path / "files" / "kelectric_schedule" / "schedule").iterdir())
    assert len(files) == 2


def test_same_bytes_without_etag_is_unchanged(tmp_path: Path) -> None:
    site = FakeSite()
    run(site, tmp_path)
    site.files[SCHED] = (b"%PDF schedule v1", "")  # server stops sending ETag
    r = run(site, tmp_path)
    assert r.count("unchanged") == 1
    assert SnapshotStore(tmp_path).records[-1].note == "same content"


def test_republished_at_new_url_is_noted(tmp_path: Path) -> None:
    site = FakeSite()
    run(site, tmp_path)
    new = "https://ke.com.pk/wp-content/uploads/2026/10/LSM-Oct.pdf"
    site.links = [new]
    site.files[new] = (b"%PDF schedule oct", "")
    r = run(site, tmp_path)
    assert r.count("changed") == 1
    assert "url changed from" in SnapshotStore(tmp_path).records[-1].note


def test_discovery_failure_reported_not_raised(tmp_path: Path) -> None:
    site = FakeSite()
    site.links = []
    r = run(site, tmp_path)
    assert not r.ok
    assert any("kelectric_schedule" in e for e in r.errors)
    assert r.count("new") == 1  # the press release still succeeds


def test_fetch_error_logged(tmp_path: Path) -> None:
    site = FakeSite()
    del site.files[SCHED]
    r = run(site, tmp_path)
    assert r.count("error") == 1
    rec = SnapshotStore(tmp_path).records
    assert any(x.http_status == 404 and not x.sha256 for x in rec)
