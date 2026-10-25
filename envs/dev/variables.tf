# Never hard-code the address. Locally, set it in an untracked terraform.tfvars
# (*.tfvars is gitignored). In CI, set the ALERT_EMAIL repository variable;
# the workflows export it as TF_VAR_alert_email. Set it in both places or
# neither: an apply without it removes the subscription.
variable "alert_email" {
  description = "Email for SLO alarm notifications; empty means no subscription"
  type        = string
  default     = ""
  # Public repo: keep the address out of plan output and CI logs.
  sensitive = true
}
