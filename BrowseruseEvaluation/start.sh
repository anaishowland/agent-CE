#!/bin/bash
set -euo pipefail

# Configuration
IMAGE_NAME="browseruse-eval"
CREDS_FILE="$HOME/.config/gcloud/application_default_credentials.json"

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Browseruse Evaluation Docker Container${NC}"
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
echo "$CREDS_FILE"

# Run the Docker container
sudo docker run \
    -v "$HOME/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json:ro" \
    -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
    -it --rm --entrypoint="" \
    "$IMAGE_NAME" \
    /bin/bash -c "
        echo -e '${GREEN}=== Container Started ===${NC}'
        echo 'Verifying environment...'
        
        # Check credentials
        if [ -f '/root/.config/gcloud/application_default_credentials.json' ]; then
            echo '✅ GCP credentials mounted successfully'
        else
            echo '❌ GCP credentials not found'
            exit 1
        fi
        
        # Check neurosim
        if python -c 'import neurosim' 2>/dev/null; then
            echo '✅ neurosim package available'
        else
            echo '❌ neurosim package not found'
            exit 1
        fi
        
        echo ''
        echo -e '${YELLOW}Starting Xvfb virtual display...${NC}'
        Xvfb :99 -screen 0 1920x1080x24 &
        XVFB_PID=\$!
        export DISPLAY=:99
        
        # Wait for Xvfb to start
        sleep 2
        
        if ps -p \$XVFB_PID > /dev/null; then
            echo '✅ Xvfb started successfully on DISPLAY=:99'
        else
            echo '❌ Failed to start Xvfb'
            exit 1
        fi
        
        echo ''
        echo -e '${GREEN}Starting Browseruse Evaluation Application...${NC}'
        echo '========================================='
        
        python -m BrowseruseEvaluation.main \\
            --jobId 'docker-job-$(date +%s)' \\
            --task 'U2VhcmNoIGZvciBhIHNwZWNpZmljIHRvcGljIG9uIEdvb2dsZSBhbmQgb3BlbiB0aGUgdG9wIDMgcmVzdWx0cy4=' \\
            --taskId 'task_001' \\
            --browser 'CHROME' \\
            --episode '0' \\
            --user 'example_user' \\
            --model 'gemini-2.5-flash-preview-05-20' \\
            --advanced_settings '{\"max_steps\": 10, \"use_vision\": true}'
    "

echo ""
echo -e "${GREEN}[COMPLETED]${NC} Browseruse Evaluation finished"