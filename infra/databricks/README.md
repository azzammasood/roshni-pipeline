# Roshni on Databricks (Terraform)

This module is optional. The production pipeline runs on DuckDB in GitHub Actions and does not
use it. It declares the Databricks objects behind the dbt `databricks` target, which built the
same models on Databricks Free Edition in October 2026 (dbt PASS=78, no dialect fixes).

It manages only what `scripts/databricks_load.py` and `roshni build --target databricks` need:

| Resource | Name (default) | Why |
|---|---|---|
| `databricks_catalog` (off by default) | `workspace` | Free Edition already has `workspace`; it is reused unless `create_catalog = true` |
| `databricks_schema.raw` | `workspace.roshni_raw` | parsed tables; dbt sources read here (`dbt/models/staging/_sources.yml`) |
| `databricks_volume.uploads` | `workspace.roshni_raw.uploads` | Parquet files PUT by `databricks_load.py` |
| `databricks_schema.dbt` | `workspace.roshni` | dbt target schema (`dbt/profiles.yml`) |
| `databricks_sql_endpoint` (only if no `existing_warehouse_id`) | `roshni-dbt` | 2X-Small, 1 cluster, serverless, stops after 5 idle minutes |
| `databricks_job.dbt_build` | `roshni-dbt-build` | serverless dbt task: checks out this repo and runs `dbt build` in `dbt/`, daily at 09:30 Asia/Karachi, **created paused** |
| `databricks_grant` (none by default) | | `USE_CATALOG`, `USE_SCHEMA`, `SELECT` for each name in `reader_principals` |

Nothing here uploads data. The raw tables still come from `databricks_load.py`, run by hand
after `roshni parse`. Until then, the job's dbt build fails on missing sources.

## Credentials

There are no credentials in this repository, and none belong in `terraform.tfvars`. The
provider reads them from the environment or from a profile:

```powershell
# Option A: environment variables (a personal access token from User settings > Developer)
$env:DATABRICKS_HOST = "https://dbc-xxxxxxxx-xxxx.cloud.databricks.com"
$env:DATABRICKS_TOKEN = "<token>"

# Option B: a profile in ~/.databrickscfg (written by `databricks auth login --host ...`)
# then set databricks_profile = "<name>" in terraform.tfvars
```

State (`terraform.tfstate`) is local and git-ignored. It holds object IDs, not tokens, but
keep it out of the repo all the same. A shared backend is not set up: one owner applies.

## Apply

Terraform 1.9 or newer. From `infra/databricks/`:

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars   # then edit: profile, warehouse ID
terraform init
terraform plan -out roshni.tfplan                      # read it before applying
terraform apply roshni.tfplan
```

Then point the CLI at the outputs and load the data:

```powershell
$env:DATABRICKS_HTTP_PATH = terraform output -raw http_path
$env:ROSHNI_DATABRICKS_CATALOG = terraform output -raw catalog
uv run roshni parse
uv run --group databricks python scripts/databricks_load.py
uv run --group databricks roshni build --target databricks
```

Run the job once by hand (Workflows > `roshni-dbt-build` > Run now). Only after a green run, set
`job_paused = false` and apply again to start the daily schedule.

### Objects that already exist

The October 2026 run created `roshni_raw`, `uploads` and `roshni` with SQL, so a first apply
on that workspace fails with "already exists". Adopt them instead of recreating them:

```powershell
terraform import databricks_schema.raw workspace.roshni_raw
terraform import databricks_volume.uploads workspace.roshni_raw.uploads
terraform import databricks_schema.dbt workspace.roshni
```

## Destroy

```powershell
terraform destroy
```

This removes the job, the grants, the volume (and the Parquet files in it), and the warehouse
if this module created it. A schema that still holds tables is not dropped unless
`force_destroy = true`. That setting drops every table in it, so use it only on purpose. A
reused warehouse (`existing_warehouse_id`) and a reused catalog (`create_catalog = false`) are
never touched.

## Free Edition

Checked against the Free Edition limits page (docs.databricks.com, "Free Edition
limitations", updated 2026-11-16):

| Resource | Free Edition | Note |
|---|---|---|
| Schemas, volume | yes | no limit listed; the 2026-10 run created both |
| Catalog | reuse `workspace` | creating a catalog is not mentioned on the limits page; it is off by default |
| SQL warehouse | **reuse the existing one** | "One SQL warehouse, limited to a 2X-Small cluster size." Free Edition starts with "Serverless Starter Warehouse", so set `existing_warehouse_id` to its ID. Creating a second warehouse needs a paid workspace (or deleting the starter one first) |
| Job | yes | serverless only ("Custom compute configurations are not supported"), which is why the job has no cluster block; at most 5 concurrent job tasks, and this job has 1 |
| Grants | yes | no limit listed; a one-person workspace has nobody else to grant to, so the default is none |
| Account-level objects | none used | Free Edition has "No access to the account console or account-level APIs"; this module uses workspace APIs only |

So no part needs a paid workspace when `existing_warehouse_id` is set. With it left null, the
module creates a warehouse, which only works on a paid workspace (or after the starter warehouse
is deleted).

## What it costs

- **Free Edition:** $0. There is no billing; usage is capped by the quotas above.
- **Paid workspace:** the objects themselves are free; compute is billed while it runs. A
  2X-Small serverless SQL warehouse is 4 DBU an hour, billed per second, and stops after 5 idle
  minutes. At a list price of roughly $0.70 per DBU (serverless SQL on AWS; check your cloud
  and region), that is about $2.80 per running hour. One `dbt build` of this project takes
  minutes, so a daily run plus idle stop costs cents a day, plus a little serverless job compute
  for the dbt runner. Storage is a few MB of Parquet and Delta tables. While the job stays paused
  and nobody queries, nothing is billed.

## What CI checks

`.github/workflows/infra.yml` runs on changes to `infra/**`: `terraform fmt -check`,
`terraform init -backend=false`, `terraform validate` and `tflint` (all rules of the terraform
ruleset). It has no Databricks credentials and never runs `plan` or `apply`. Whether the
workspace accepts each object (names, quotas, the dbt task's generated profile) is only proven
by an apply.
