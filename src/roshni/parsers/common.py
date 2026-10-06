"""Shared parser types: provenance, quarantine, Parquet output."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel

from roshni.sources.inventory import sha256_of


class Provenance(BaseModel):
    source_file: str
    source_sha256: str
    fetched_at: datetime | None  # UTC; None when unknown (hand-downloaded, no snapshot record)


def provenance(path: Path, fetched_at: datetime | None = None) -> Provenance:
    return Provenance(source_file=path.name, source_sha256=sha256_of(path), fetched_at=fetched_at)


class QuarantineRow(BaseModel):
    source_file: str
    source_sha256: str
    location: str  # "row 17", "page 3 line 42", ...
    raw: str
    reason: str


@dataclass
class ParseResult[T: BaseModel]:
    table: str
    rows: list[T] = field(default_factory=list)
    quarantine: list[QuarantineRow] = field(default_factory=list)

    def reject(self, prov: Provenance, location: str, raw: str, reason: str) -> None:
        self.quarantine.append(
            QuarantineRow(
                source_file=prov.source_file,
                source_sha256=prov.source_sha256,
                location=location,
                raw=raw[:2000],
                reason=reason,
            )
        )

    def extend(self, other: "ParseResult[T]") -> None:
        self.rows.extend(other.rows)
        self.quarantine.extend(other.quarantine)


def _to_table(models: list[BaseModel], model_cls: type[BaseModel]) -> pa.Table:
    if models:
        return pa.Table.from_pylist([m.model_dump() for m in models])
    return pa.Table.from_pylist([], schema=_empty_schema(model_cls))


def _empty_schema(model_cls: type[BaseModel]) -> pa.Schema:
    return pa.schema([(name, pa.string()) for name in model_cls.model_fields])


def write_result(result: ParseResult, row_cls: type[BaseModel], out_dir: Path) -> dict[str, Path]:
    """Write <out>/<table>.parquet and <out>/quarantine/<table>.parquet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "quarantine").mkdir(exist_ok=True)
    main = out_dir / f"{result.table}.parquet"
    quar = out_dir / "quarantine" / f"{result.table}.parquet"
    pq.write_table(_to_table(result.rows, row_cls), main)
    pq.write_table(_to_table(result.quarantine, QuarantineRow), quar)
    return {"rows": main, "quarantine": quar}
