output "catalog" {
  description = "Catalog: set ROSHNI_DATABRICKS_CATALOG to this."
  value       = local.catalog
}

output "warehouse_id" {
  description = "SQL warehouse used by dbt and the job."
  value       = local.warehouse_id
}

output "http_path" {
  description = "Set DATABRICKS_HTTP_PATH to this for scripts/databricks_load.py and `roshni build --target databricks`."
  value       = "/sql/1.0/warehouses/${local.warehouse_id}"
}

output "volume_path" {
  description = "Where scripts/databricks_load.py puts the Parquet files."
  value       = "/Volumes/${local.catalog}/${databricks_schema.raw.name}/${databricks_volume.uploads.name}"
}

output "job_id" {
  description = "Job that runs dbt build (its schedule stays paused unless job_paused = false)."
  value       = databricks_job.dbt_build.id
}
