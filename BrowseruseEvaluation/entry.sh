#!/bin/bash
echo "All arguments: $@"

# decode_task_args.sh - Function library for decoding task arguments
# Usage: source decode_task_args.sh

# Function to decode base64 (modify this based on your encoding scheme)
decode_task_value() {
    local encoded="$1"
    # Example: base64 decode
    echo "$encoded" | base64 -d 2>/dev/null || echo "$encoded"
    # Alternative decoding methods:
    # echo "$encoded" | xxd -r -p  # hex decode
    # python3 -c "import urllib.parse; print(urllib.parse.unquote('$encoded'))"  # URL decode
}

# Main function to decode --task arguments in place
# Usage: decode_task_args "$@"
# Returns: Sets global DECODED_ARGS array and DECODED_TASK variable
decode_task_args() {
    local args=("$@")
    local print_only=false
    local skip_next=false
    local found_task=false
    
    # Check if print-only mode
    for arg in "${args[@]}"; do
        if [[ "$arg" == "--print-only" ]]; then
            print_only=true
            break
        fi
    done
    
    # Initialize global arrays
    DECODED_ARGS=()
    DECODED_TASK=""
    
    # Process arguments
    for arg in "${args[@]}"; do
        if [[ "$arg" == "--print-only" ]]; then
            # Skip --print-only flag, don't add to DECODED_ARGS
            continue
        elif [[ "$skip_next" == true ]]; then
            # This is an encoded task value, decode ONLY this argument
            DECODED_TASK=$(decode_task_value "$arg")
            found_task=true
            
            if [[ "$print_only" == true ]]; then
                echo "$DECODED_TASK"
                return 0
            else
                DECODED_ARGS+=("$DECODED_TASK")  # Add decoded task
            fi
            skip_next=false
        elif [[ "$arg" == "--task" ]]; then
            DECODED_ARGS+=("$arg")  # Add --task flag as-is
            skip_next=true
        else
            DECODED_ARGS+=("$arg")  # Add all other arguments as-is (no decoding)
        fi
    done
    
    # Check if we ended with --task but no value
    if [[ "$skip_next" == true ]]; then
        echo "Error: --task flag without value" >&2
        return 1
    fi
    
    # Return success if task was found and decoded
    if [[ "$found_task" == true ]]; then
        return 0
    else
        return 2  # No --task flag found
    fi
}

# Convenience function to get just the decoded task value
# Usage: get_decoded_task "$@"
get_decoded_task() {
    local temp_args=("$@" "--print-only")
    decode_task_args "${temp_args[@]}"
}

# Convenience function to replace arguments in place
# Usage: replace_task_args_inplace "$@"
# Sets the positional parameters to the decoded arguments
replace_task_args_inplace() {
    if decode_task_args "$@"; then
        set -- "${DECODED_ARGS[@]}"
        export DECODED_ARGS
        export DECODED_TASK
        echo "Arguments decoded successfully. Use \$DECODED_TASK for the decoded task value." >&2
        return 0
    else
        echo "No --task argument found or decoding failed." >&2
        return 1
    fi
}

# Example usage function (remove this in production)
example_usage() {
    echo "=== Example Usage ==="
    echo
    echo "# Method 1: Get just the decoded task"
    echo 'decoded_task=$(get_decoded_task --task "SGVsbG8gV29ybGQ=" --verbose)'
    echo 'echo "Task: $decoded_task"'
    echo
    echo "# Method 2: Decode all arguments"
    echo 'decode_task_args "$@"'
    echo 'echo "Original: $*"'
    echo 'echo "Decoded: ${DECODED_ARGS[*]}"'
    echo 'echo "Task: $DECODED_TASK"'
    echo
    echo "# Method 3: Replace positional parameters"
    echo 'replace_task_args_inplace "$@"'
    echo 'echo "New arguments: $*"'
    echo 'echo "Decoded task: $DECODED_TASK"'
}

# Main execution function - run xvfb with decoded arguments
run_with_decoded_args() {
    # Check if no arguments provided, use defaults
    if [ $# -eq 0 ]; then
        echo "No arguments provided, running with defaults..." >&2
        xvfb-run -a python -m BrowseruseEvaluation.main \
            --jobId "docker-job-$(date +%s)" \
            --task "open apple.com" \
            --taskId "task_001" \
            --browser "chrome" \
            --episode "0" \
            --user "test-user" \
            --model "gemini-2.5-flash-preview-05-20" \
            --advanced_settings '{"max_steps": 10, "use_vision": true}'
    fi
    
    if decode_task_args "$@"; then
        echo "Decoded args: ${DECODED_ARGS[*]}" >&2
        echo "Running with decoded arguments..." >&2
        
        # If advanced settings were provided via env var, append as CLI
        if [[ -n "${ADVANCED_SETTINGS_B64:-}" ]]; then
            ADV_JSON="$(echo "$ADVANCED_SETTINGS_B64" | base64 -d 2>/dev/null || true)"
            if [[ -n "$ADV_JSON" ]]; then
                DECODED_ARGS+=("--advanced_settings" "$ADV_JSON")
                echo "Injected advanced settings from ADVANCED_SETTINGS_B64" >&2
                echo "Advanced settings (decoded): $ADV_JSON" >&2
            fi
        fi

        # Execute xvfb-run with the decoded arguments
        xvfb-run -a python -m BrowseruseEvaluation.main "${DECODED_ARGS[@]}"
    else
        local exit_code=$?
        case $exit_code in
            1) echo "Error: Invalid --task usage" >&2; exit 1 ;;
            2) 
                echo "No --task found, running with original arguments..." >&2
                xvfb-run -a python -m BrowseruseEvaluation.main "$@"
                ;;
        esac
    fi
}

# If script is run directly (not sourced), run the main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Always run with decoded args (handles both no args and with args cases)
    run_with_decoded_args "$@"
fi