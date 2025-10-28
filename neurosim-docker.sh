#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="neurosim-base"
DOCKERFILE="Dockerfile.base" # adjust if your file is named differently

# Get short-lived token for build process
echo "[INFO] Getting GCP access token for build..."
TOKEN=$(gcloud auth application-default print-access-token)

# Build the Docker image with the token as build argument
echo "[INFO] Building image: $IMAGE_NAME using $DOCKERFILE with GCP token"
sudo DOCKER_BUILDKIT=1 docker build \
    --build-arg GCLOUD_ACCESS_TOKEN="$TOKEN" \
    -t "$IMAGE_NAME" \
    -f "$DOCKERFILE" \
    .

echo "[INFO] Build completed successfully!"

# Run the container with GCP credentials mounted (if arguments provided)
if [ $# -gt 0 ]; then
    echo "[INFO] Running container with credentials..."
    sudo docker run -it --rm \
        -v "$HOME/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json:ro" \
        -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
        "$IMAGE_NAME" "$@"
else
    echo "[INFO] Build only mode - container not started"
    echo "[INFO] To run the container, use: sudo docker run -it --rm $IMAGE_NAME [command]"
fi