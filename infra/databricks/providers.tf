# No credentials in this repo. The provider takes host and profile from the variables below
# (both optional), then DATABRICKS_HOST with DATABRICKS_TOKEN (or DATABRICKS_CLIENT_ID and
# DATABRICKS_CLIENT_SECRET), then a profile in ~/.databrickscfg. See README.md.
provider "databricks" {
  host    = var.databricks_host
  profile = var.databricks_profile
}
