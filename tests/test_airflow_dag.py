"""The Airflow DAG must stay orchestration-only: every task is one roshni CLI command.

Checked statically (Airflow is not installed in the project environment)."""

import ast
import re

from typer.main import get_command

from roshni.cli import app
from roshni.paths import REPO_ROOT

DAG = REPO_ROOT / "airflow" / "dags" / "roshni_pipeline.py"


def steps() -> list[tuple[str, str]]:
    tree = ast.parse(DAG.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "STEPS":
            return ast.literal_eval(node.value)
    raise AssertionError("STEPS not found")


def test_dag_tasks_are_cli_commands() -> None:
    commands = set(get_command(app).commands)
    found = steps()
    assert [t for t, _ in found] == ["snapshot", "parse", "validate", "build", "report", "export"]
    for _, args in found:
        assert args.split()[0] in commands


def test_dag_has_no_business_logic() -> None:
    src = DAG.read_text(encoding="utf-8")
    assert not re.search(r"\b(duckdb|pandas|select |httpx|requests)\b", src)
    assert "schedule=None" in src  # GitHub Actions is the production scheduler
