terraform {
  required_version = ">=1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# 1. Pub/Sub topic for Live Flight Telemetry
resource "google_pubsub_topic" "flights_stream" {
  name = "flights-stream"
}

# 2. Pub/Sub Topic for Air Quality Readings
resource "google_pubsub_topic" "air_quality_stream" {
  name = "air-quality-stream"
}

resource "google_bigquery_dataset" "geo_analytics" {
  dataset_id                 = "geo_analytics"
  friendly_name              = "Geo Analytics Storage"
  description                = "Dataset for flight telemetry and air quality spatial join analytics."
  location                   = var.gcp_region
  delete_contents_on_destroy = true # Set to false for strict production durability
}
