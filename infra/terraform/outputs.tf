output "flights_topic_id" {
  description = "Pub/Sub topic ID for flights"
  value       = google_pubsub_topic.flights_stream.id
}

output "air_quality_topic_id" {
  description = "Pub/Sub topic ID for air quality"
  value       = google_pubsub_topic.air_quality_stream.id
}

output "bigquery_dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.geo_analytics.dataset_id
}
