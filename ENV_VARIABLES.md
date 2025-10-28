# Environment Variables Reference

This document lists all environment variables used by Agent-CE.

## Required Variables

### Google Cloud Storage

```bash
# Your GCS bucket name for storing evaluation results
GCS_BUCKET_NAME=your-gcs-bucket-name

# Path to your GCP service account JSON key file
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
```

### LLM API Keys

At least one is required depending on which agent you're using:

```bash
# OpenAI API key (for Browser Use, OpenAI Computer Use)
OPENAI_API_KEY=your_openai_api_key

# Anthropic API key (for Anthropic Computer Use)
ANTHROPIC_API_KEY=your_anthropic_api_key

# Google AI API key (for Gemini models)
GOOGLE_API_KEY=your_google_api_key
```

## Optional Variables

### Google Cloud Project

```bash
# Your GCP project ID
GCP_PROJECT_ID=your-gcp-project-id
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```

### Firestore Configuration

```bash
# Firestore database name
FIRESTORE_DATABASE=(default)

# Firestore collection for evaluation status
FIRESTORE_COLLECTION=agent-eval-status
```

### Evaluation Configuration

```bash
# Job identifier
JOB_ID=job_001

# Task description
TASK=Navigate to google.com

# Task identifier
TASK_ID=task_001

# Browser channel: CHROME, CHROMIUM, MSEDGE
BROWSER=CHROME

# Episode number
EPISODE=0

# User identifier
USER_NAME=user_001

# Model to use
MODEL=gpt-4o
```

### Advanced Settings

```bash
# Advanced agent settings (JSON format)
ADVANCED_SETTINGS={"max_steps": 50, "use_vision": true, "temperature": 0.0}
```

Common settings:
- `max_steps`: Maximum number of agent steps (default: 50)
- `max_actions_per_step`: Max actions per step (default: 10)
- `max_retries`: Max retries on failure (default: 2)
- `use_vision`: Enable vision for multimodal models (default: true)
- `temperature`: LLM temperature (default: 0.0)
- `generate_gif`: Generate GIF of execution (Browser Use only, default: false)

### Logging

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO
```

### Cloud Run Deployment

```bash
# Task index for parallel execution
CLOUD_RUN_TASK_INDEX=0

# Total number of tasks
CLOUD_RUN_TASK_COUNT=1

# Cloud Run job name
CLOUD_RUN_JOB=evaluation-job
```

### GitHub Integration (CI/CD)

```bash
# GitHub token for cloning private repos
GH_TOKEN=your_github_token

# GitHub repository (format: owner/repo)
GH_REPO=your-org/your-agent-repo
```

### Anthropic Vertex AI

```bash
# Vertex AI project ID
ANTHROPIC_VERTEX_PROJECT_ID=your-vertex-project-id

# Vertex AI region
ANTHROPIC_VERTEX_REGION=us-central1
```

### Browser Configuration

```bash
# Browser profile settings (JSON)
BROWSER_PROFILE={"headless": false, "keep_alive": false}

# Browser headless mode
BROWSER_HEADLESS=false
```

### Development

```bash
# Skip GCS upload for local testing
SKIP_GCS_UPLOAD=true

# Enable debug mode
DEBUG=true
```

## Agent-Specific Variables

### Browser Use

```bash
MODEL=gpt-4o  # or claude-3-5-sonnet-20241022, gemini-2.5-flash-preview-05-20
ADVANCED_SETTINGS={"max_steps": 50, "use_vision": true, "generate_gif": false}
```

### Notte

```bash
MODEL=gpt-4o  # or other supported models
NOTTE_CONFIG_PATH=./NotteEvaluation/notte_config.toml
```

### Anthropic Computer Use

```bash
ANTHROPIC_API_KEY=your_key
MODEL=claude-3-5-sonnet-20241022
```

### OpenAI Computer Use

```bash
OPENAI_API_KEY=your_key
MODEL=gpt-4o
```

## Creating a .env File

Create a `.env` file in your project root:

```bash
# Required
GCS_BUCKET_NAME=my-bucket
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
OPENAI_API_KEY=sk-...

# Optional
LOG_LEVEL=INFO
JOB_ID=test_job_001
```

Then:

```bash
# Load in shell
export $(cat .env | xargs)

# Or let Python handle it
python -c "from dotenv import load_dotenv; load_dotenv()"
```

## Docker Environment

When running in Docker, pass variables with `-e`:

```bash
docker run --rm \
    -e GCS_BUCKET_NAME=my-bucket \
    -e OPENAI_API_KEY=sk-... \
    -v ~/.config/gcloud:/root/.config/gcloud:ro \
    your-agent-image
```

Or use `--env-file`:

```bash
docker run --rm --env-file .env your-agent-image
```

