"""Golden-set evaluation for Ask Roshni (config/ask_golden.yml), per model.

Scoring is by execution, not by SQL text: the model's query result must contain the reference
result (see `matches`). Refusal, guard and reject items check the behaviour instead. Per model we
report accuracy, refusal/guard correctness, narration pass rate, tokens and latency (mean, p95), so
the provider chain order in config/llm.yml is chosen from evidence.
"""

import json
import math
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import duckdb
import yaml

from roshni import evalrecord
from roshni.ask import engine, semantic, sqlguard
from roshni.llm.chain import ChainConfig
from roshni.paths import CONFIG_DIR, REPO_ROOT

GOLDEN = CONFIG_DIR / "ask_golden.yml"
EVAL_RECORD = REPO_ROOT / "evals" / "ask_roshni.json"
FLOOR_PCT = 90.0  # a weekly score below this is posted as a notice
# expect: reject -> must not be answered: blocked by the prompt guard, refused by the planner, or
# every query stopped by the SQL guard. Scored with the guard items.
GUARD_EXPECT = ("block", "reject")


def _norm(v) -> str:
    if v is None:
        return "null"
    s = str(v).replace(",", "").strip()
    try:  # half-up on the decimal text, as DuckDB's ROUND does (10.25 -> 10.3)
        return str(Decimal(s).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) + 0)
    except InvalidOperation:
        return s.lower()


def matches(ref_cols: list[str], ref_rows: list, got_cols: list[str], got_rows: list,
            ordered: bool = False) -> bool:  # fmt: skip
    """True if every reference column maps to a distinct result column with the same values,
    and the projected rows are equal (as a multiset, or in order). Small references (at most
    four cells, e.g. a pivoted 'six vs twelve' answer) also pass when every reference measure
    value (all columns but the first) appears among the result's cells."""
    ref = [tuple(_norm(v) for v in r) for r in ref_rows]
    got = [tuple(_norm(v) for v in r) for r in got_rows]
    if len(ref) == len(got):
        used: set[int] = set()
        mapping: list[int] = []
        for i in range(len(ref_cols)):
            want = sorted(r[i] for r in ref)
            j = next(
                (j for j in range(len(got_cols))
                 if j not in used and sorted(g[j] for g in got) == want),
                None,
            )  # fmt: skip
            if j is None:
                break
            used.add(j)
            mapping.append(j)
        else:
            proj = [tuple(g[j] for j in mapping) for g in got]
            if (proj == ref) if ordered else (Counter(proj) == Counter(ref)):
                return True
    # Pivoted small answers: compare the measure columns (all but the first, the key).
    cells = [v for r in ref for v in (r[1:] if len(r) > 1 else r)]
    if len(ref) * len(ref_cols) <= 4 and got and len(got) != len(ref):
        have = Counter(v for g in got for v in g)
        return not (Counter(cells) - have)
    return False


@dataclass
class ItemScore:
    id: str
    expect: str
    status: str
    correct: bool
    narrated: bool
    tokens: int
    latency_s: float
    detail: str = ""


@dataclass
class ModelScore:
    model: str
    items: list[ItemScore] = field(default_factory=list)

    def summary(self) -> dict:
        def rate(xs: list[ItemScore]) -> float | None:
            return round(100 * sum(x.correct for x in xs) / len(xs), 1) if xs else None

        ans = [i for i in self.items if i.expect == "answer"]
        lat = sorted(i.latency_s for i in self.items if i.status != "blocked")
        return {
            "model": self.model,
            "items": len(self.items),
            "answer_accuracy_pct": rate(ans),
            "refusal_accuracy_pct": rate([i for i in self.items if i.expect == "refuse"]),
            "guard_accuracy_pct": rate([i for i in self.items if i.expect in GUARD_EXPECT]),
            "overall_pct": rate(self.items),
            "narration_pass_pct": rate(
                [
                    ItemScore(i.id, "", "", i.narrated, False, 0, 0)
                    for i in ans
                    if i.status == "answered"
                ]
            ),  # fmt: skip
            "tokens_total": sum(i.tokens for i in self.items),
            "latency_mean_s": round(statistics.mean(lat), 2) if lat else None,
            "latency_p95_s": round(lat[min(len(lat), math.ceil(0.95 * len(lat))) - 1], 2)
            if lat
            else None,
        }


def load_items(path: Path = GOLDEN) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["items"]


def evaluate(
    con: duckdb.DuckDBPyConnection,
    cfg: ChainConfig,
    model: str,
    items: list[dict],
    layer: semantic.SemanticLayer,
    pause_s: float = 0.0,
    log=print,
) -> ModelScore:
    pinned = cfg.pinned(model)
    score = ModelScore(model)
    for it in items:
        res = engine.ask(it["question"], con, pinned, layer)
        expect = it["expect"]
        detail = ""
        if expect == "answer":
            ref = sqlguard.run(con, sqlguard.check(it["sql"], layer).sql)
            ok = res.status == "answered" and matches(
                ref.columns, ref.rows, res.columns, res.rows, bool(it.get("ordered"))
            )
            if not ok:
                detail = res.sql or res.reason
        elif expect == "refuse":
            ok = res.status == "refused"
            detail = "" if ok else (res.sql or res.reason)
        elif expect == "reject":
            ok = res.status != "answered"
            detail = "" if ok else (res.sql or "")
        else:
            ok = res.status == "blocked"
        narrated = res.narrated_by != "template"
        s = ItemScore(it["id"], expect, res.status, ok, narrated, res.tokens, res.latency_s,
                      detail[:300])  # fmt: skip
        score.items.append(s)
        log(f"  {'PASS' if ok else 'FAIL'} {it['id']:28} {res.status:8} {res.tokens:5} tok "
            f"{res.latency_s:5.2f}s {detail[:90]}")  # fmt: skip
        if pause_s:
            time.sleep(pause_s)  # stay under the free plan's tokens-per-minute cap
    return score


def write(scores: list[ModelScore], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    js = out_dir / f"ask_eval_{stamp}.json"
    js.write_text(
        json.dumps(
            {
                "run_at": stamp,
                "summary": [s.summary() for s in scores],
                "items": {s.model: [i.__dict__ for i in s.items] for s in scores},
            },
            indent=2,
        ),  # fmt: skip
        encoding="utf-8",
    )
    head = ["model", "overall %", "answer %", "refuse %", "guard %", "narration %", "tokens",
            "mean s", "p95 s"]  # fmt: skip
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for s in scores:
        m = s.summary()
        lines.append(
            f"| {m['model']} | {m['overall_pct']} | {m['answer_accuracy_pct']} | "
            f"{m['refusal_accuracy_pct']} | {m['guard_accuracy_pct']} | "
            f"{m['narration_pass_pct']} | {m['tokens_total']:,} | {m['latency_mean_s']} | "
            f"{m['latency_p95_s']} |"
        )
    md = out_dir / f"ask_eval_{stamp}.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md, js


RECORD_KEYS = ("model", "items", "overall_pct", "answer_accuracy_pct", "refusal_accuracy_pct",
               "guard_accuracy_pct", "narration_pass_pct", "tokens_total", "latency_mean_s",
               "latency_p95_s")  # fmt: skip


def record(
    scores: list[ModelScore], path: Path = EVAL_RECORD, today: date | None = None
) -> tuple[Path, list[str]]:
    """Update the committed record: these models' latest rows (other models are kept) and one
    history point each. Returns the path and the regression notice lines."""
    day = today or date.today()
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"models": []}
    keep = {s.model for s in scores}
    rows = [{k: s.summary()[k] for k in RECORD_KEYS} for s in scores]
    data["models"] = sorted(
        [r for r in data["models"] if r["model"] not in keep] + rows,
        key=lambda r: (-(r["overall_pct"] or 0), r["model"]),
    )
    data["run_on"] = str(day)
    evalrecord.append(
        data,
        [evalrecord.point(day, s.model, sum(i.correct for i in s.items), len(s.items))
         for s in scores],
    )  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path, evalrecord.regressions(data, day, FLOOR_PCT, "Ask Roshni golden set")
