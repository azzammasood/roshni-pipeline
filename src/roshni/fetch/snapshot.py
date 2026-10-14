"""Snapshot job: discover targets, fetch politely, store changed files, log every check."""

import dataclasses
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

import httpx

from roshni.fetch.discover import DISCOVERERS, DiscoveryError, Target
from roshni.fetch.http import FetchRefused, PoliteClient
from roshni.fetch.store import SnapshotRecord, SnapshotStore
from roshni.fetch.trim import TRIMMERS, TrimError
from roshni.sources.registry import Registry

Outcome = Literal["new", "changed", "unchanged", "known", "gap", "error"]


@dataclass
class ItemResult:
    source: str
    item_key: str
    outcome: Outcome
    detail: str = ""


@dataclass
class RunReport:
    items: list[ItemResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # discovery or policy failures
    warnings: list[str] = field(default_factory=list)

    def count(self, outcome: Outcome) -> int:
        return sum(1 for i in self.items if i.outcome == outcome)

    @property
    def ok(self) -> bool:
        return not self.errors and self.count("error") == 0

    def summary_line(self) -> str:
        outcomes = ("new", "changed", "unchanged", "known", "gap", "error")
        parts = [f"{o}={self.count(o)}" for o in outcomes]
        return " ".join(parts) + f" discovery_errors={len(self.errors)}"


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def discover(client: PoliteClient, registry: Registry, only: set[str] | None, report: RunReport):
    pages: dict[str, str] = {}
    targets: list[Target] = []
    for name, cfg in registry.sources.items():
        if only and name not in only:
            continue
        try:
            html = None
            if cfg.listing_url:
                if cfg.listing_url not in pages:
                    resp = client.get(cfg.listing_url)
                    resp.raise_for_status()
                    pages[cfg.listing_url] = resp.text
                html = pages[cfg.listing_url]
            found = DISCOVERERS[cfg.discovery](name, cfg, html)
        except (DiscoveryError, FetchRefused, httpx.HTTPError) as e:
            report.errors.append(f"{name}: {type(e).__name__}: {e}")
            continue
        for t in found:
            report.warnings.extend(f"{name}/{t.item_key}: {w}" for w in t.warnings)
        targets.extend(
            dataclasses.replace(t, trim=cfg.trim, known_broken=t.url in cfg.known_broken)
            for t in found
        )
    return targets


def snapshot_target(
    client: PoliteClient, store: SnapshotStore, t: Target, now: Callable[[], datetime] = _now
) -> ItemResult:
    if not t.refetch and store.has_url(t.url):
        return ItemResult(t.source, t.item_key, "known")

    prev = store.last_good(t.source, t.item_key)
    headers: dict[str, str] = {}
    if prev and prev.url == t.url:
        if prev.etag:
            headers["If-None-Match"] = prev.etag
        if prev.last_modified:
            headers["If-Modified-Since"] = prev.last_modified

    at = now()
    base = dict(source=t.source, item_key=t.item_key, label=t.label, url=t.url, fetched_at=_iso(at))
    try:
        resp = client.get(t.url, headers=headers or None)
    except (FetchRefused, httpx.HTTPError) as e:
        store.append(SnapshotRecord(**base, note=f"{type(e).__name__}: {e}"[:300]))
        return ItemResult(t.source, t.item_key, "error", str(e))

    meta = dict(
        http_status=resp.status_code,
        etag=resp.headers.get("etag", ""),
        last_modified=resp.headers.get("last-modified", ""),
    )
    if resp.status_code == 304 and prev:
        store.append(
            SnapshotRecord(
                **base,
                http_status=304,
                etag=meta["etag"] or prev.etag,
                last_modified=meta["last_modified"] or prev.last_modified,
                sha256=prev.sha256,
                bytes=prev.bytes,
                path=prev.path,
                note="not modified",
            )
        )
        return ItemResult(t.source, t.item_key, "unchanged", "304")
    if resp.status_code in (404, 410) and t.known_broken:
        store.append(SnapshotRecord(**base, **meta, note="known broken link (data-audit.md)"))
        return ItemResult(
            t.source, t.item_key, "gap", f"HTTP {resp.status_code}, known broken link"
        )
    if resp.status_code != 200:
        store.append(SnapshotRecord(**base, **meta, note="unexpected status"))
        return ItemResult(t.source, t.item_key, "error", f"HTTP {resp.status_code}")

    content = resp.content
    ext = None
    if t.trim:
        try:
            content = TRIMMERS[t.trim](content, t.source)
        except TrimError as e:
            store.append(SnapshotRecord(**base, **meta, note=f"not stored: {e}"[:300]))
            return ItemResult(t.source, t.item_key, "error", str(e))
        ext = ".json"
    sha = hashlib.sha256(content).hexdigest()
    notes = []
    if prev and prev.url != t.url:
        notes.append(f"url changed from {prev.url}")
    if prev and prev.sha256 == sha:
        store.append(
            SnapshotRecord(
                **base,
                **meta,
                sha256=sha,
                bytes=len(content),
                path=prev.path,
                note="; ".join(["same content", *notes]),
            )
        )
        return ItemResult(t.source, t.item_key, "unchanged", "same sha256")

    path = store.write_file(t.source, t.item_key, t.url, content, sha, at, ext=ext)
    outcome: Outcome = "changed" if prev else "new"
    if prev:
        notes.insert(0, f"content changed from {prev.sha256[:12]}")
    store.append(
        SnapshotRecord(
            **base,
            **meta,
            sha256=sha,
            bytes=len(content),
            path=path,
            changed=True,
            note="; ".join(notes),
        )
    )
    return ItemResult(t.source, t.item_key, outcome, f"{len(content)} bytes")


def run_snapshot(
    client: PoliteClient, store: SnapshotStore, registry: Registry, only: set[str] | None = None
) -> RunReport:
    report = RunReport()
    for t in discover(client, registry, only, report):
        report.items.append(snapshot_target(client, store, t))
    return report
