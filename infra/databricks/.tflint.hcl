# The bundled terraform ruleset, every rule. There is no Databricks-specific tflint ruleset.
plugin "terraform" {
  enabled = true
  preset  = "all"
}
