"""Roshni pipeline as an Airflow DAG: orchestration only.

Every task is one `roshni` CLI command, the same commands GitHub Actions runs in production.
No business logic lives here. The DAG is unscheduled (manual trigger): GitHub Actions is the
production scheduler; this is the local orchestration showcase.
"""

import os
from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

ROSHNI = os.environ.get("ROSHNI_BIN", "roshni")

STEPS = [
    ("snapshot", "snapshot --store /opt/roshni/data/snapshots"),
    ("parse", "parse --snapshots /opt/roshni/data/snapshots"),
    ("validate", "validate"),
    ("build", "build"),
    ("report", "report --engine auto"),  # LLM only if OPENROUTER_API_KEY is set
    ("export", "export"),
]

with DAG(
    dag_id="roshni_pipeline",
    description="Snapshot -> parse -> GE validate -> dbt build -> report -> static export",
    schedule=None,
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["roshni", "showcase"],
) as dag:
    previous = None
    for task_id, args in STEPS:
        task = BashOperator(task_id=task_id, bash_command=f"{ROSHNI} {args}")
        if previous is not None:
            previous >> task
        previous = task
