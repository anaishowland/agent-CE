#!/bin/bash
set -e

# Echo the values
echo "Task ID: $TASK_ID"
echo "Task description (base64): $TASK_DESCRIPTION"
echo "Episode: $EPISODE"
echo "Model: computer-use-preview"
echo "User: $USER_ID"
echo "Job ID: $JOB_ID"
echo "Task Index: $TASK_INDEX"
echo "Total Tasks: $TOTAL_TASKS"

# Decode base64 task description
if [ -z "$TASK_DESCRIPTION" ]; then
    echo "Error: TASK_DESCRIPTION is empty" >&2
    exit 1
fi

TASK_DESCRIPTION_DECODED=$(echo "$TASK_DESCRIPTION" | base64 -d) || {
    echo "Error: Failed to decode base64 TASK_DESCRIPTION" >&2
    exit 1
}
echo "Decoded task description: $TASK_DESCRIPTION_DECODED"

# Execute the task
# Allow overriding max steps via env, default to 50
MAX_STEPS=${MAX_STEPS:-50}
xvfb-run -a python -m OpenaiEvaluation.main \
    --jobId "$JOB_ID" \
    --task "$TASK_DESCRIPTION_DECODED" \
    --taskId "$TASK_ID" \
    --user "$USER_ID" \
    --episode "$EPISODE" \
    --model "computer-use-preview" \
    --advanced_settings '{"episode": '"$EPISODE"', "temperature": 0.00, "max_steps": 50, "max_action_per_step": 10, "max_retries": 3, "use_vision": true}'
