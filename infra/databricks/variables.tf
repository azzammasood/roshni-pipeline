variable "databricks_host" {
  description = "Workspace URL, e.g. https://dbc-1234abcd-5678.cloud.databricks.com. Null: use DATABRICKS_HOST or the profile."
  type        = string
  default     = null
}

variable "databricks_profile" {
  description = "Profile name in ~/.databrickscfg. Null: use environment variables."
  type        = string
  default     = null
}

variable "catalog_name" {
  description = "Unity Catalog catalog for both schemas. Same value as ROSHNI_DATABRICKS_CATALOG (default \"workspace\", the catalog Free Edition creates)."
  type        = string
  default     = "workspace"
}

variable "create_catalog" {
  description = "Create catalog_name. False (default): use an existing catalog, such as Free Edition's \"workspace\"."
  type        = bool
  default     = false
}

variable "raw_schema_name" {
  description = "Schema for the uploaded parsed tables. Must stay \"roshni_raw\" unless dbt/models/staging/_sources.yml and scripts/databricks_load.py change with it."
  type        = string
  default     = "roshni_raw"
}

variable "dbt_schema_name" {
  description = "dbt target schema (seeds, staging views, marts). Same value as `schema` in dbt/profiles.yml."
  type        = string
  default     = "roshni"
}

variable "volume_name" {
  description = "Managed volume in the raw schema that receives the Parquet uploads. Same value as VOLUME in scripts/databricks_load.py."
  type        = string
  default     = "uploads"
}

variable "existing_warehouse_id" {
  description = "ID of a SQL warehouse to reuse. Free Edition allows one warehouse and already has \"Serverless Starter Warehouse\": pass its ID there. Null: create one."
  type        = string
  default     = null
}

variable "warehouse_name" {
  description = "Name of the SQL warehouse created when existing_warehouse_id is null."
  type        = string
  default     = "roshni-dbt"
}

variable "warehouse_auto_stop_mins" {
  description = "Idle minutes before the created warehouse stops."
  type        = number
  default     = 5

  validation {
    condition     = var.warehouse_auto_stop_mins >= 1 && var.warehouse_auto_stop_mins <= 30
    error_message = "Keep auto-stop between 1 and 30 minutes: an idle warehouse costs money on a paid workspace."
  }
}

variable "job_name" {
  description = "Name of the Databricks job that runs dbt build."
  type        = string
  default     = "roshni-dbt-build"
}

variable "git_url" {
  description = "Public Git repository the dbt task checks out."
  type        = string
  default     = "https://github.com/azzammasood/roshni-pipeline"
}

variable "git_branch" {
  description = "Branch the dbt task checks out."
  type        = string
  default     = "main"
}

variable "dbt_databricks_requirement" {
  description = "pip requirement for the job's serverless environment. Keep in step with the databricks group in pyproject.toml."
  type        = string
  default     = "dbt-databricks>=1.12.6,<2"
}

variable "job_schedule_cron" {
  description = "Quartz cron for the daily run, in Asia/Karachi time. Default 09:30."
  type        = string
  default     = "0 30 9 * * ?"
}

variable "job_paused" {
  description = "Create the daily schedule paused. Set false only after a manual run succeeds."
  type        = bool
  default     = true
}

variable "force_destroy" {
  description = "Let `terraform destroy` drop the schemas even when they still hold tables. False: destroy stops at a non-empty schema."
  type        = bool
  default     = false
}

variable "reader_principals" {
  description = "Users or groups given read access (USE CATALOG, USE SCHEMA, SELECT) to the dbt schema. Empty by default."
  type        = set(string)
  default     = []
}
