#!/bin/bash
set -euo pipefail

# Configuration
IMAGE_NAME="notte-eval"
CREDS_FILE="$HOME/.config/gcloud/application_default_credentials.json"

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Notte Evaluation Docker Container${NC}"
echo "=============================================="

# Check if credentials file exists
if [ ! -f "$CREDS_FILE" ]; then
    echo -e "${RED}[ERROR]${NC} GCP credentials not found at: $CREDS_FILE"
    echo "Please run: gcloud auth application-default login"
    exit 1
fi

# Check if Docker image exists
if ! sudo docker images "$IMAGE_NAME" | grep -q "$IMAGE_NAME"; then
    echo -e "${RED}[ERROR]${NC} Docker image '$IMAGE_NAME' not found"
    echo "Please build the image first with: sudo docker build -t $IMAGE_NAME ."
    exit 1
fi

echo -e "${YELLOW}[INFO]${NC} Using credentials: $CREDS_FILE"
echo -e "${YELLOW}[INFO]${NC} Using Docker image: $IMAGE_NAME"
echo ""

# Run the Docker container
sudo docker run \
    -v "$CREDS_FILE:/root/.config/gcloud/application_default_credentials.json:ro" \
    -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
    -e GOOGLE_CLOUD_PROJECT=your-gcp-project-id \
    -it --rm \
    "$IMAGE_NAME" \

echo ""
echo -e "${GREEN}[COMPLETED]${NC} Notte Evaluation finished"