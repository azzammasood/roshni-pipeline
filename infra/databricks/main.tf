# Roshni on Databricks: only what scripts/databricks_load.py and the dbt `databricks` target
# need. Nothing here uploads data: the raw tables still come from databricks_load.py.

locals {
  catalog      = var.create_catalog ? databricks_catalog.roshni[0].name : var.catalog_name
  warehouse_id = var.existing_warehouse_id != null ? var.existing_warehouse_id : databricks_sql_endpoint.dbt[0].id
}

# --- Unity Catalog -------------------------------------------------------------------------

resource "databricks_catalog" "roshni" {
  count   = var.create_catalog ? 1 : 0
  name    = var.catalog_name
  comment = "Roshni pipeline (managed by infra/databricks)"
}

resource "databricks_schema" "raw" {
  catalog_name  = local.catalog
  name          = var.raw_schema_name
  comment       = "Parsed Parquet uploaded by scripts/databricks_load.py; read by dbt sources"
  force_destroy = var.force_destroy
}

resource "databricks_schema" "dbt" {
  catalog_name  = local.catalog
  name          = var.dbt_schema_name
  comment       = "dbt target: seeds, staging views, marts"
  force_destroy = var.force_destroy
}

resource "databricks_volume" "uploads" {
  catalog_name = local.catalog
  schema_name  = databricks_schema.raw.name
  name         = var.volume_name
  volume_type  = "MANAGED"
  comment      = "Parquet files PUT by scripts/databricks_load.py"
}

# --- Compute -------------------------------------------------------------------------------

# Created only when no existing warehouse is given. Smallest size, one cluster, serverless.
resource "databricks_sql_endpoint" "dbt" {
  count                     = var.existing_warehouse_id == null ? 1 : 0
  name                      = var.warehouse_name
  cluster_size              = "2X-Small"
  min_num_clusters          = 1
  max_num_clusters          = 1
  auto_stop_mins            = var.warehouse_auto_stop_mins
  enable_serverless_compute = true
  warehouse_type            = "PRO"

  tags {
    custom_tags {
      key   = "project"
      value = "roshni"
    }
  }
}

# --- Job -----------------------------------------------------------------------------------

# Serverless job (no cluster block): the only job compute Free Edition offers. The dbt task
# checks out the public repo and runs the project in dbt/ on the SQL warehouse. With no
# profiles_directory, Databricks writes the dbt profile from warehouse_id, catalog and schema
# and runs as the job owner, so no token is stored anywhere.
resource "databricks_job" "dbt_build" {
  name                = var.job_name
  description         = "dbt build (seeds, models, tests) of the Roshni warehouse; the same models as `roshni build --target databricks`."
  max_concurrent_runs = 1
  timeout_seconds     = 3600

  git_source {
    url      = var.git_url
    provider = "gitHub"
    branch   = var.git_branch
  }

  environment {
    environment_key = "dbt"
    spec {
      environment_version = "2"
      dependencies        = [var.dbt_databricks_requirement]
    }
  }

  task {
    task_key        = "dbt_build"
    environment_key = "dbt"

    dbt_task {
      source            = "GIT"
      project_directory = "dbt"
      commands          = ["dbt build"]
      warehouse_id      = local.warehouse_id
      catalog           = local.catalog
      schema            = databricks_schema.dbt.name
    }
  }

  schedule {
    quartz_cron_expression = var.job_schedule_cron
    timezone_id            = "Asia/Karachi"
    pause_status           = var.job_paused ? "PAUSED" : "UNPAUSED"
  }

  tags = {
    project = "roshni"
  }

  # dbt reads its sources from the raw schema, filled through the volume.
  depends_on = [databricks_volume.uploads]
}

# --- Grants --------------------------------------------------------------------------------

# Read-only access for extra principals (none by default). The applying identity owns
# everything above and needs no grant. databricks_grant is authoritative only for one
# principal on one securable, so other principals' grants are left alone.
resource "databricks_grant" "catalog_use" {
  for_each   = var.reader_principals
  catalog    = local.catalog
  principal  = each.value
  privileges = ["USE_CATALOG"]
}

resource "databricks_grant" "dbt_read" {
  for_each   = var.reader_principals
  schema     = databricks_schema.dbt.id
  principal  = each.value
  privileges = ["USE_SCHEMA", "SELECT"]
}
