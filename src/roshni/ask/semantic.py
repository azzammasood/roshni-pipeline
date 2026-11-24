"""Semantic layer: allowlisted tables/columns (config/semantic_layer.yml) + dbt descriptions."""

from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import yaml

from roshni.paths import CONFIG_DIR, REPO_ROOT

DBT_MODELS = REPO_ROOT / "dbt" / "models"


@dataclass
class Column:
    name: str
    description: str = ""
    note: str = ""
    auto_values: bool = False


@dataclass
class Table:
    name: str
    description: str
    note: str
    columns: dict[str, Column]
    caveats: list[str] = field(default_factory=list)


@dataclass
class SemanticLayer:
    rules: list[str]
    tables: dict[str, Table]

    def allowed_columns(self, tables: set[str] | None = None) -> set[str]:
        names = tables if tables is not None else set(self.tables)
        return {c for t in names if t in self.tables for c in self.tables[t].columns}

    def caveats_for(self, tables: set[str]) -> list[str]:
        out: list[str] = []
        for t in sorted(tables):
            for c in self.tables[t].caveats if t in self.tables else []:
                if c not in out:
                    out.append(c)
        return out

    def prompt_context(self, con: duckdb.DuckDBPyConnection | None = None) -> str:
        """Compact schema text for the planner; `values: auto` columns list their values."""
        lines = ["Rules:", *[f"- {r}" for r in self.rules], "", "Tables (DuckDB):"]
        for t in self.tables.values():
            lines.append(f"\n{t.name}: {t.description} {t.note}".rstrip())
            for c in t.columns.values():
                desc = " ".join(x for x in (c.description, c.note) if x)
                if c.auto_values and con is not None:
                    try:
                        vals = con.execute(
                            f'select distinct "{c.name}" from {t.name} '  # allowlisted names
                            f'where "{c.name}" is not null order by 1 limit 26'
                        ).fetchall()
                    except duckdb.Error:  # table absent (tests, partial builds): no values
                        vals = [None] * 26
                    if len(vals) <= 25:
                        desc += " Values: " + ", ".join(repr(v[0]) for v in vals) + "."
                lines.append(f"  - {c.name}: {desc}".rstrip())
        return "\n".join(lines)


def dbt_docs(models_dir: Path = DBT_MODELS) -> dict[str, dict]:
    """{model: {"description": str, "columns": {col: description}}} from every dbt yml."""
    out: dict[str, dict] = {}
    for path in sorted(models_dir.rglob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for m in data.get("models") or []:
            cols = {c["name"]: (c.get("description") or "").strip() for c in m.get("columns") or []}
            out[m["name"]] = {"description": (m.get("description") or "").strip(), "columns": cols}
    return out


def load(path: Path | None = None, models_dir: Path = DBT_MODELS) -> SemanticLayer:
    raw = yaml.safe_load((path or CONFIG_DIR / "semantic_layer.yml").read_text(encoding="utf-8"))
    docs = dbt_docs(models_dir)
    tables: dict[str, Table] = {}
    for name, spec in raw["tables"].items():
        doc = docs.get(name, {"description": "", "columns": {}})
        cols = {
            c: Column(
                c,
                " ".join(doc["columns"].get(c, "").split()),
                (cspec or {}).get("note", ""),
                (cspec or {}).get("values") == "auto",
            )
            for c, cspec in spec["columns"].items()
        }
        tables[name] = Table(
            name,
            " ".join(doc["description"].split()),
            " ".join((spec.get("note") or "").split()),
            cols,
            [" ".join(c.split()) for c in spec.get("caveats") or []],
        )
    return SemanticLayer([" ".join(r.split()) for r in raw["rules"]], tables)
