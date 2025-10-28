#!/bin/bash
set -euo pipefail

# Default: Direct API key path; enable Vertex only if requested
if [[ "${ANTHROPIC_USE_VERTEX:-false}" =~ ^(1|true|yes|TRUE|YES)$ ]]; then
  echo "[ENTRY] Anthropic Vertex mode"
  export ANTHROPIC_VERTEX_REGION="${ANTHROPIC_VERTEX_REGION:-global}"
  echo "Task ID: ${TASK_ID:-}"
  echo "Task description (base64): ${TASK_DESCRIPTION:-}"
  echo "Episode: ${EPISODE:-}"
  echo "Model: claude-sonnet-4-20250514"
  echo "User: ${USER_ID:-}"
  echo "Job ID: ${JOB_ID:-}"

  if [ -z "${TASK_DESCRIPTION:-}" ]; then
    echo "Error: TASK_DESCRIPTION is empty" >&2
    exit 1
  fi
  TASK_DESCRIPTION_DECODED=$(echo "$TASK_DESCRIPTION" | base64 -d) || {
    echo "Error: Failed to decode base64 TASK_DESCRIPTION" >&2
    exit 1
  }
  echo "Decoded task description: $TASK_DESCRIPTION_DECODED"

  xvfb-run -a python -m AnthropicEvaluation.main \
    --jobId "${JOB_ID:-anthropic}" \
    --task "$TASK_DESCRIPTION_DECODED" \
    --taskId "${TASK_ID:-task}" \
    --user "${USER_ID:-local}" \
    --episode "${EPISODE:-0}" \
    --model "claude-sonnet-4-20250514" \
    --advanced_settings '{"episode": '"${EPISODE:-0}"', "temperature": 0.00, "max_steps": 50, "max_action_per_step": 10, "max_retries": 3, "use_vision": true}'
  exit 0
fi

echo "[ENTRY] Direct API mode"
# Check if TASK_INDEX is provided
if [ -z "${TASK_INDEX:-}" ]; then
  echo "Error: TASK_INDEX environment variable is not set." >&2
  exit 1
fi

# Determine which API key to use based on TASK_INDEX
if [ $((${TASK_INDEX} % 2)) -eq 0 ]; then
  echo "Task Index is even, using ANTHROPIC_API_KEY_2."
  export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY_2:-}"
else
  echo "Task Index is odd, using ANTHROPIC_API_KEY_1."
  export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY_1:-}"
fi

# Check if the final ANTHROPIC_API_KEY is set
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "Error: ANTHROPIC_API_KEY is not set. Make sure ANTHROPIC_API_KEY_1 or ANTHROPIC_API_KEY_2 is provided." >&2
  exit 1
fi

# Echo the values for debugging
echo "Task ID: ${TASK_ID:-}"
echo "Task description (base64): ${TASK_DESCRIPTION:-}"
echo "Episode: ${EPISODE:-}"
echo "Model: claude-sonnet-4-20250514"
echo "User: ${USER_ID:-}"
echo "Job ID: ${JOB_ID:-}"
echo "Task Index: ${TASK_INDEX:-}"
echo "Total Tasks: ${TOTAL_TASKS:-}"

# Decode base64 task description
if [ -z "${TASK_DESCRIPTION:-}" ]; then
  echo "Error: TASK_DESCRIPTION is empty" >&2
  exit 1
fi

TASK_DESCRIPTION_DECODED=$(echo "$TASK_DESCRIPTION" | base64 -d) || {
  echo "Error: Failed to decode base64 TASK_DESCRIPTION" >&2
  exit 1
}
echo "Decoded task description: $TASK_DESCRIPTION_DECODED"

# Execute the task
xvfb-run -a python -m AnthropicEvaluation.main \
  --jobId "${JOB_ID:-anthropic}" \
  --task "$TASK_DESCRIPTION_DECODED" \
  --taskId "${TASK_ID:-task}" \
  --user "${USER_ID:-local}" \
  --episode "${EPISODE:-0}" \
  --model "claude-sonnet-4-20250514" \
  --advanced_settings '{"episode": '"${EPISODE:-0}"', "temperature": 0.00, "max_steps": 50, "max_action_per_step": 10, "max_retries": 3, "use_vision": true}'

