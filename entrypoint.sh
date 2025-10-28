#!/bin/bash
set -e

# Verify neurosim is available (should be since it's installed during build)
if python -c "import neurosim" 2>/dev/null; then
    echo "[INFO] neurosim package is available"
else
    echo "[ERROR] neurosim package not found - this shouldn't happen if build was successful"
    exit 1
fi

# Execute the command passed to the container
exec "$@"