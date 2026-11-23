terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    # Exact pin; bump deliberately. CI runs fmt, init, validate and tflint on infra/**.
    databricks = {
      source  = "databricks/databricks"
      version = "1.143.0"
    }
  }
}
