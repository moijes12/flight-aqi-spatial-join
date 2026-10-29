variable "gcp_project_id" {
  type        = string
  description = "Your Google Cloud Project ID"
}

variable "gcp_region" {
  description = "GCP Region for resource deployment"
  type        = string
  default     = "us-central1"
}
