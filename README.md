# Agent-CE: Continuous Evaluation Platform for Web Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)](https://www.python.org/downloads/)

**Agent-CE** is a containerized continuous evaluation (CE) platform for web browsing agents. It provides production-ready Docker images and CI/CD pipelines for running and evaluating multiple agent frameworks including Browser Use, Notte, Anthropic Computer Use, and OpenAI Computer Use.

**Developed at Paradigm Shift AI**

**Contributors**: Anais Howland, Ashwin Thinnappan, Vaibhav Gupta, Maithili Hebbar (Anthropic & OpenAI CUA), Jameel Shahid Mohammed

## Features

- **4 Pre-Integrated Agent Frameworks**:
  - [Browser Use](https://github.com/browser-use/browser-use): Playwright-based browser automation
  - [Notte](https://github.com/nottelabs/notte): Advanced web agent framework
  - Anthropic Computer Use: Claude-powered browser agent
  - OpenAI Computer Use: GPT-powered browser agent

- **Dockerized Execution**: Each agent runs in isolated containers for consistency and reproducibility
- **GitHub Actions CI/CD**: Automated Docker image building and deployment
- **Cloud Run Integration**: Scalable deployment on GCP Cloud Run
- **Structured Result Format**: Compatible with neurosim LLM judge system
- **Multi-Episode Evaluation**: Run agents across multiple episodes with different configurations

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Agent Implementations](#agent-implementations)
- [Docker Images](#docker-images)
- [CI/CD Pipeline](#cicd-pipeline)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [Citation](#citation)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│         GitHub Repository (Your Agents)             │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Browser Use │  │    Notte     │  │ Anthropic │ │
│  │             │  │              │  │    CUA    │ │
│  └─────────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────┘
                        │
            GitHub Webhook / Dispatch
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│          GitHub Actions CI/CD Pipeline              │
│  ┌───────────────────────────────────────────────┐ │
│  │ 1. Build base image (neurosim-base)           │ │
│  │ 2. Build agent-specific images                │ │
│  │ 3. Push to Container Registry                 │ │
│  │ 4. Trigger evaluation jobs                    │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│     Container Registry (GCR/Artifact Registry)      │
│                                                     │
│  neurosim-base:latest                              │
│  browser-use/{branch}:{tag}                        │
│  notte/{branch}:{tag}                              │
│  anthropic-cua:latest                              │
│  openai-cua:latest                                 │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│      Execution Environment (Cloud Run/Local)        │
│  ┌──────────────────────────────────────────────┐  │
│  │  Docker Container (per task/episode)         │  │
│  │  ┌──────────────────────────────────────┐   │  │
│  │  │  Agent Execution                     │   │  │
│  │  │  • Run browser automation            │   │  │
│  │  │  • Capture screenshots               │   │  │
│  │  │  • Track tokens & latency            │   │  │
│  │  │  • Upload results to GCS             │   │  │
│  │  └──────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│        Google Cloud Storage + Firestore             │
│  • Results (JSON, compressed with zstd)            │
│  • Screenshots (PNG)                               │
│  • Job status tracking                             │
│  • Metrics aggregation                             │
└─────────────────────────────────────────────────────┘
```

### Component Dependencies

```
agent-CE (this repo)
    │
    ├── Depends on: neurosim package
    │   └── Provides: Evaluation base class, GCS storage, models
    │
    ├── Base Docker Image: neurosim-base
    │   └── Includes: Python 3.11, neurosim package, system deps
    │
    └── Agent Images: Built on neurosim-base
        ├── browser-use: + Playwright + Chrome
        ├── notte: + Notte package + Chrome
        ├── anthropic-cua: + Anthropic SDK + Playwright
        └── openai-cua: + OpenAI SDK + Playwright
```

## Prerequisites

### Required

- Python 3.11+
- Docker (for building/running containers)
- Google Cloud Platform account with:
  - Google Cloud Storage (GCS) bucket
  - Artifact Registry or Container Registry
  - (Optional) Cloud Run for deployment
  - Service account with appropriate permissions

### Optional

- GitHub account (for CI/CD integration)
- Firestore database (for status tracking)

## Installation

### 1. Clone the Repositories

You need both `neurosim` (core framework) and `agent-CE` (agent implementations):

```bash
# Clone neurosim (dependency)
git clone https://github.com/anaishowland/neurosim.git
cd neurosim
pip install -e ".[core]"
cd ..

# Clone agent-CE
git clone https://github.com/anaishowland/agent-CE.git
cd agent-CE
```

### 2. Set Up Google Cloud

```bash
# Authenticate with Google Cloud
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Create a GCS bucket for results
gsutil mb gs://YOUR_BUCKET_NAME

# Create Artifact Registry repository (if using GCP)
gcloud artifacts repositories create agents \
    --repository-format=docker \
    --location=us-central1 \
    --description="Agent evaluation images"
```

### 3. Configure Environment

Create a `.env` file:

```bash
# Required
GCS_BUCKET_NAME=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Optional: Firestore
GCP_PROJECT_ID=your-project-id
FIRESTORE_DATABASE=(default)
FIRESTORE_COLLECTION=evaluations

# Optional: LLM API Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# Optional: Advanced settings
LOG_LEVEL=INFO
CLOUD_RUN_TASK_INDEX=0
```

## Quick Start

### Local Execution (Single Agent)

1. **Browser Use Agent**:

```bash
cd BrowseruseEvaluation

# Install dependencies
pip install browser-use playwright
playwright install chrome

# Run evaluation
python main.py \
    --jobId job_001 \
    --task "Navigate to google.com and search for 'AI agents'" \
    --taskId task_001 \
    --user user_001 \
    --episode 0 \
    --model gpt-4o \
    --advanced_settings '{"max_steps": 50, "use_vision": true}'
```

2. **Notte Agent**:

```bash
cd NotteEvaluation

# Install dependencies
pip install notte playwright
playwright install chrome

# Run evaluation (similar CLI)
python main.py --jobId job_001 ...
```

### Docker Execution

#### Build Base Image

```bash
# Requires neurosim to be installed/available
chmod +x neurosim-docker.sh
./neurosim-docker.sh
```

#### Build and Run Agent Image

```bash
# Build Browser Use image
cd BrowseruseEvaluation
docker build -t browser-use-eval -f Dockerfile .

# Run container
docker run --rm \
    -e GCS_BUCKET_NAME=your-bucket \
    -e OPENAI_API_KEY=your_key \
    -v ~/.config/gcloud:/root/.config/gcloud:ro \
    browser-use-eval \
    python main.py --jobId job_001 --task "..." --taskId task_001 --user user_001 --episode 0
```

## Agent Implementations

### 1. Browser Use

**Framework**: [browser-use](https://github.com/browser-use/browser-use)  
**LLM Support**: OpenAI, Anthropic, Google Gemini  
**Features**: Vision support, memory, GIF generation

**Configuration**:
```json
{
  "max_steps": 50,
  "max_actions_per_step": 10,
  "max_retries": 2,
  "use_vision": true,
  "generate_gif": false
}
```

### 2. Notte

**Framework**: [notte](https://github.com/nottelabs/notte)  
**LLM Support**: OpenAI, Anthropic, Google Gemini  
**Features**: Advanced web navigation, custom configurations

**Configuration**:
```toml
# notte_config.toml
[notte]
browser = "chromium"
headless = true
# ... additional settings
```

### 3. Anthropic Computer Use

**Framework**: Anthropic's computer use API  
**LLM**: Claude 4.0 Sonnet (or later)  
**Features**: Native computer use capabilities

### 4. OpenAI Computer Use

**Framework**: Custom implementation using OpenAI's models  
**LLM**: GPT-4, GPT-4o  
**Features**: Playwright-based browser control

## Docker Images

### Image Hierarchy

```
neurosim-base (Base Image)
    ├── Python 3.11-slim
    ├── neurosim package
    ├── System dependencies (X11, fonts, etc.)
    └── Entry point script

agent-specific images (Built on neurosim-base)
    ├── browser-use: + browser-use + playwright + Chrome
    ├── notte: + notte + playwright + Chrome
    ├── anthropic-cua: + anthropic + playwright + Chrome
    └── openai-cua: + openai + playwright + Chrome
```

### Building Images

**Base Image**:
```bash
# Requires GCP authentication for neurosim package
./neurosim-docker.sh
```

**Browser Use** (standard):
```bash
cd BrowseruseEvaluation
docker build -t browser-use-eval -f Dockerfile .
```

**Browser Use** (CE - custom branch):
```bash
# For testing specific browser-use branches
docker build \
    -f CE/Dockerfile.browser_use \
    --build-arg BROWSER_USE_BRANCH=your-branch \
    --build-arg GH_TOKEN=your_github_token \
    --build-arg GH_REPO=your-org/browser-use \
    -t browser-use-ce:your-branch \
    .
```

**Notte** (CE):
```bash
docker build \
    -f CE/Dockerfile.notte \
    --build-arg NOTTE_BRANCH=main \
    -t notte-ce:latest \
    .
```

### Image Tags

```
neurosim-base:latest
browser-use:latest
notte:latest
anthropic-cua:latest
openai-cua:latest

# CE images with versioning
browser-use/{branch}:{commit-sha}
notte/{branch}:{commit-sha}
```

## CI/CD Pipeline

### GitHub Actions Workflows

1. **docker-build.yml**: Main build pipeline
   - Builds neurosim-base image
   - Builds all 4 agent images
   - Pushes to Artifact Registry
   - Triggers on PR/merge to main

2. **browser_use-image-updated.yaml**: Triggered by repository dispatch
   - Builds Browser Use with specific branch/commit
   - Supports custom GitHub repos (for forks)
   - Updates Firestore with build status

3. **notte-image-updated.yml**: Triggered by repository dispatch
   - Builds Notte with specific branch/commit
   - Similar to browser_use workflow

### Setting Up CI/CD

1. **GitHub Secrets** (add to your repository):
   ```
   GCP_SA_KEY: Service account JSON key with permissions:
     - Artifact Registry Writer
     - Storage Object Admin
     - Cloud Run Admin (if deploying)
     - Firestore User (optional)
   ```

2. **Update Workflow Files**: Replace placeholders with your values:
   ```yaml
   env:
     PROJECT_ID: your-gcp-project-id
     GAR_REGION: us-central1  # your region
     GAR_REPOSITORY: agents   # your repository name
   ```

3. **Firestore Action** (optional): Configure `.github/actions/firestore-data/action.yml`

### Triggering CE Builds

Use GitHub's repository dispatch API:

```bash
curl -X POST \
  https://api.github.com/repos/YOUR_USERNAME/agent-CE/dispatches \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "browser-use",
    "client_payload": {
      "branch": "main",
      "commit": "abc123",
      "pipeline_id": "pipeline_001",
      "job_id": "job_001",
      "user_id": "user_001",
      "model": "gpt-4o",
      "advanced_settings": "{\"max_steps\": 50}",
      "episodes": 3
    }
  }'
```

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `GCS_BUCKET_NAME` | Yes | Google Cloud Storage bucket | - |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes* | Path to GCP service account key | - |
| `GCP_PROJECT_ID` | No | GCP project ID | - |
| `FIRESTORE_DATABASE` | No | Firestore database name | `(default)` |
| `FIRESTORE_COLLECTION` | No | Firestore collection | - |
| `OPENAI_API_KEY` | No** | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | No** | Anthropic API key | - |
| `GOOGLE_API_KEY` | No** | Google AI API key | - |
| `LOG_LEVEL` | No | Logging level | `INFO` |
| `CLOUD_RUN_TASK_INDEX` | No | Task index for Cloud Run | `0` |

\* Or use `gcloud auth application-default login`  
\** Required based on which agent/model you're using

### Advanced Settings (JSON)

Pass to agents via `--advanced_settings` CLI argument:

```json
{
  "max_steps": 50,
  "max_actions_per_step": 10,
  "max_retries": 2,
  "temperature": 0.0,
  "use_vision": true,
  "generate_gif": false,
  "episode": 0
}
```

### Dockerfile Configuration

**Base Image** (`Dockerfile.base`):
- Replace `PYTHON_REPO_URL` with your artifact registry URL (or remove if using public PyPI)
- Update `GCS_BUCKET_NAME` default value

**Agent Images**:
- Update base image references if using custom registry

## Usage Examples

### Example 1: Run Browser Use Locally

```python
import asyncio
from neurosim.utils.models import EvaluationRequest
from BrowseruseEvaluation.main import BrowseruseEvaluation

request = EvaluationRequest(
    userid="user123",
    model="gpt-4o",
    jobid="job_20250101_001",
    task="Go to news.ycombinator.com and find the top story",
    taskid="task_001",
    browser_channel="chrome",
    episode=0,
    advanced_settings={"max_steps": 30, "use_vision": True},
    bucket_name="my-eval-results"
)

eval_instance = BrowseruseEvaluation(request)
asyncio.run(eval_instance.execute())
```

### Example 2: Batch Evaluation

```python
import asyncio

tasks = [
    "Open google.com",
    "Navigate to github.com and search for 'AI agents'",
    "Go to wikipedia.org and search for 'Machine Learning'"
]

for i, task in enumerate(tasks):
    request = EvaluationRequest(
        userid="user123",
        model="gpt-4o",
        jobid=f"batch_job_001",
        task=task,
        taskid=f"task_{i:03d}",
        browser_channel="chrome",
        episode=0,
        advanced_settings={},
        bucket_name="my-eval-results"
    )
    
    eval_instance = BrowseruseEvaluation(request)
    await eval_instance.execute()
```

### Example 3: Multi-Episode Evaluation

```bash
# Run same task 5 times with different episodes
for episode in {0..4}; do
    docker run --rm \
        -e GCS_BUCKET_NAME=my-bucket \
        -e OPENAI_API_KEY=$OPENAI_API_KEY \
        -v ~/.config/gcloud:/root/.config/gcloud:ro \
        browser-use-eval \
        python main.py \
            --jobId job_001 \
            --task "Navigate to google.com" \
            --taskId task_001 \
            --user user_001 \
            --episode $episode \
            --model gpt-4o
done
```

## Development

### Project Setup

```bash
# Install neurosim in editable mode
cd ../neurosim
pip install -e ".[core,judge]"

# Return to agent-CE
cd ../agent-CE

# Install agent-specific dependencies
pip install browser-use notte playwright anthropic openai
playwright install chrome
```

### Adding a New Agent

1. Create agent directory: `YourAgent/`
2. Implement `main.py` extending `neurosim.evaluation.Evaluation`
3. Create `Dockerfile` based on `neurosim-base`
4. Add `requirements.txt`
5. Create `entry.sh` entrypoint script
6. Add to CI/CD pipeline in `.github/workflows/docker-build.yml`

**Example structure**:
```
YourAgent/
├── main.py              # Evaluation implementation
├── llm.py               # LLM configuration
├── Dockerfile           # Container definition
├── requirements.txt     # Python dependencies
├── entry.sh             # Entry point script
└── Makefile            # Build automation (optional)
```

### Testing Locally

```bash
# Test agent directly
cd BrowseruseEvaluation
python main.py --jobId test_001 --task "..." --taskId task_001 --user dev --episode 0

# Test with Docker
docker build -t test-browser-use .
docker run --rm -e GCS_BUCKET_NAME=test-bucket test-browser-use python main.py ...
```

## Troubleshooting

### Common Issues

#### 1. neurosim package not found

**Error**: `ModuleNotFoundError: No module named 'neurosim'`

**Solution**:
```bash
cd ../neurosim
pip install -e ".[core]"
```

#### 2. GCS Authentication Failed

**Error**: `google.auth.exceptions.DefaultCredentialsError`

**Solution**:
```bash
# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

# Or use gcloud
gcloud auth application-default login
```

#### 3. Docker Build Fails (neurosim-base)

**Error**: Build fails when installing neurosim

**Solution**: Ensure you have a valid GCP token:
```bash
# Get token
gcloud auth application-default print-access-token

# Build with token
export GCLOUD_ACCESS_TOKEN=$(gcloud auth application-default print-access-token)
docker build --build-arg GCLOUD_ACCESS_TOKEN=$GCLOUD_ACCESS_TOKEN -f Dockerfile.base -t neurosim-base .
```

#### 4. Playwright Browser Not Found

**Error**: `Executable doesn't exist`

**Solution**:
```bash
playwright install chrome
# or in Docker, ensure RUN playwright install chrome is in Dockerfile
```

#### 5. GitHub Actions CI/CD Issues

**Error**: Workflow fails with permission errors

**Solution**: Check that your GCP service account has these roles:
- Artifact Registry Writer
- Storage Object Admin
- (Optional) Cloud Run Admin
- (Optional) Firestore User

### Additional Resources

- [neurosim documentation](https://github.com/anaishowland/neurosim) - Core evaluation framework
- Agent-specific documentation (Browser Use, Notte, etc.)
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design details

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use this work, please cite:

```bibtex
@software{agentce2025,
  author = {Howland, Anais and Thinnappan, Ashwin and Gupta, Vaibhav and Hebbar, Maithili and Mohammed, Jameel Shahid},
  title = {Agent-CE: Continuous Evaluation Platform for Web Agents},
  year = {2025},
  publisher = {Paradigm Shift AI},
  url = {https://github.com/anaishowland/agent-CE}
}
```

**Developed at Paradigm Shift AI**

This project was created to provide a production-ready continuous evaluation platform for web browsing agents.

## About This Release

This is a snapshot release of work developed at Paradigm Shift AI. The code is provided as-is under the MIT License for the community to use, modify, and build upon.
