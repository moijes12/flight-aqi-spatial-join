from google.cloud import secretmanager


def access_latest_secret(project_id: str, secret_id: str) -> str:
    """Read version ``latest`` of a Secret Manager secret."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8").strip()
