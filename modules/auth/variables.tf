variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "callback_urls" {
  description = "Where Cognito may send users after login"
  type        = list(string)
  default     = ["http://localhost:3000/callback"]
}

variable "logout_urls" {
  type    = list(string)
  default = ["http://localhost:3000/"]
}

variable "groups" {
  description = "Role groups: name => description"
  type        = map(string)
  default = {
    developers = "Full access: public, partners, develop"
    operations = "Full access: public, partners"
    testers    = "Read-only: public, partners"
    partner_a  = "Public read, own partner folder read/write"
    partner_b  = "Public read, own partner folder read/write"
  }
}
