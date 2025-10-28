# Agent-CE Architecture

This document describes the architecture of the Agent-CE (Continuous Evaluation) platform.

## Overview

Agent-CE is a Docker-based continuous evaluation platform for web browsing agents. It provides:

1. **Agent Implementations**: Pre-integrated agents (Browser Use, Notte, Anthropic CUA, OpenAI CUA)
2. **Containerization**: Docker images for isolated, reproducible execution
3. **CI/CD Pipeline**: GitHub Actions for automated builds and deployments
4. **Cloud Integration**: GCP Cloud Run for scalable execution

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               GitHub Repository (Your Agents)                │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ Browser    │  │    Notte   │  │ Anthropic  │           │
│  │    Use     │  │            │  │    CUA     │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
                        │
        GitHub Webhook / Repository Dispatch
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│             GitHub Actions CI/CD Pipeline                    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Build neurosim-base image                        │  │
│  │     └─ Python 3.11 + neurosim + system deps          │  │
│  │                                                       │  │
│  │  2. Build agent-specific images (parallel)           │  │
│  │     ├─ browser-use: base + Browser Use + Chrome      │  │
│  │     ├─ notte: base + Notte + Chrome                  │  │
│  │     ├─ anthropic-cua: base + Anthropic SDK           │  │
│  │     └─ openai-cua: base + OpenAI SDK                 │  │
│  │                                                       │  │
│  │  3. Push to Container Registry                       │  │
│  │     └─ Artifact Registry / GCR                       │  │
│  │                                                       │  │
│  │  4. Trigger evaluation jobs (optional)               │  │
│  │     └─ Cloud Run / External CE platform              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│          Container Registry (Artifact Registry)              │
│                                                              │
│  neurosim-base:latest                                       │
│  browser-use/{branch}:{tag}                                 │
│  notte/{branch}:{tag}                                       │
│  anthropic-cua:latest                                       │
│  openai-cua:latest                                          │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           Execution Environment (Cloud Run)                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Container Instance (per task)                       │  │
│  │  ┌────────────────────────────────────────────────┐ │  │
│  │  │  Agent Execution                               │ │  │
│  │  │  1. Initialize agent (Browser Use/Notte/etc.)  │ │  │
│  │  │  2. Run task                                   │ │  │
│  │  │  3. Capture screenshots                        │ │  │
│  │  │  4. Track tokens & latency                     │ │  │
│  │  │  5. Upload results to GCS                      │ │  │
│  │  └────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│          Google Cloud Storage + Firestore                    │
│  • Results (JSON, zstd compressed)                          │
│  • Screenshots (PNG)                                        │
│  • Job status (Firestore)                                   │
│  • Metrics aggregation                                      │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Base Image (neurosim-base)

**Dockerfile**: `Dockerfile.base`

The foundation for all agent images:

```dockerfile
FROM python:3.11-slim

# System dependencies (X11, fonts, etc.)
# Python tooling (uv)
# neurosim package installation
# Base entrypoint script
```

**Contents**:
- Python 3.11-slim base
- System dependencies: X11, xvfb (for headless browsers)
- UV package manager for fast installs
- neurosim package (from private registry or PyPI)
- Base entrypoint script

**Build Process**:
```bash
# Requires GCP authentication token
./neurosim-docker.sh

# Or manually
docker build \
    --build-arg GCLOUD_ACCESS_TOKEN=$(gcloud auth print-access-token) \
    -f Dockerfile.base \
    -t neurosim-base \
    .
```

### 2. Agent Implementations

Each agent extends `neurosim.evaluation.Evaluation`:

#### Browser Use

**Directory**: `BrowseruseEvaluation/`  
**Framework**: [browser-use](https://github.com/browser-use/browser-use)  
**LLMs**: OpenAI, Anthropic, Google Gemini

**Key Files**:
- `main.py`: Evaluation implementation
- `llm.py`: LLM configuration (GPT, Claude, Gemini)
- `Dockerfile`: Container definition
- `entry.sh`: Entrypoint script

**Features**:
- Vision support (multimodal models)
- GIF generation of execution
- Memory/history tracking
- Configurable browser profiles

#### Notte

**Directory**: `NotteEvaluation/`  
**Framework**: [notte](https://github.com/nottelabs/notte)  
**LLMs**: OpenAI, Anthropic, Google Gemini

**Key Files**:
- `main.py`: Evaluation implementation
- `notte_config.toml`: Notte configuration
- `Dockerfile`: Container definition

**Features**:
- Advanced web navigation
- Custom configurations via TOML
- Patchright (Playwright fork) integration

#### Anthropic Computer Use

**Directory**: `AnthropicEvaluation/`  
**API**: Anthropic's Computer Use API  
**LLM**: Claude 4.0 Sonnet+

**Key Files**:
- `main.py`: Evaluation implementation
- `Dockerfile`: Container definition

**Features**:
- Native computer use capabilities
- Screenshot-based interaction
- Playwright integration

#### OpenAI Computer Use

**Directory**: `OpenaiEvaluation/`  
**API**: Custom implementation with OpenAI  
**LLMs**: GPT-4o, GPT-5

**Key Files**:
- `main.py`: Evaluation implementation
- `actions_playwright.py`: Browser actions
- `Dockerfile`: Container definition

**Features**:
- Playwright-based browser control
- Custom action primitives
- Screenshot-based reasoning

### 3. CI/CD Pipeline

#### Main Build Workflow

**File**: `.github/workflows/docker-build.yml`

**Triggers**:
- Pull request to main
- Push to main
- Manual workflow dispatch
- Schedule (optional)

**Steps**:
1. **Build neurosim-base**:
   - Get GCP auth token
   - Build base image
   - Push to Artifact Registry

2. **Build agent images** (parallel matrix):
   - Browser Use
   - Notte
   - Anthropic CUA
   - OpenAI CUA

3. **Tag and push**:
   - `:latest` tag
   - Version/commit tags (optional)

#### Continuous Evaluation Workflows

**Browser Use**: `.github/workflows/browser_use-image-updated.yaml`  
**Notte**: `.github/workflows/notte-image-updated.yml`

**Trigger**: Repository dispatch events

**Payload**:
```json
{
  "branch": "main",
  "commit": "abc123",
  "pipeline_id": "pipe_001",
  "job_id": "job_001",
  "user_id": "user_001",
  "model": "gpt-4o",
  "advanced_settings": "{\"max_steps\": 50}",
  "episodes": 3
}
```

**Steps**:
1. Extract payload
2. Authenticate with GCP
3. Update Firestore status (PACKAGING)
4. Get GitHub token (if private repo)
5. Build Docker image
6. Push to registry
7. POST to CE platform (optional)
8. Update Firestore status (SUCCESS/FAILED)

#### Custom Actions

**Firestore Data**: `.github/actions/firestore-data/action.yml`

Updates Firestore documents with build/execution status:
- Status: PACKAGING, RUNNING, SUCCESS, FAILED
- Timestamps
- Build metadata

### 4. Docker Images

#### Image Hierarchy

```
python:3.11-slim
    │
    ├─ neurosim-base
    │   ├─ System deps (X11, fonts)
    │   ├─ UV package manager
    │   ├─ neurosim package
    │   └─ Base entrypoint
    │
    ├─ browser-use:latest
    │   ├─ neurosim-base
    │   ├─ browser-use package
    │   ├─ playwright
    │   ├─ Chrome browser
    │   └─ BrowseruseEvaluation code
    │
    ├─ notte:latest
    │   ├─ neurosim-base
    │   ├─ notte package
    │   ├─ patchright
    │   ├─ Chrome browser
    │   └─ NotteEvaluation code
    │
    ├─ anthropic-cua:latest
    │   ├─ neurosim-base
    │   ├─ anthropic SDK
    │   ├─ playwright
    │   ├─ Chrome browser
    │   └─ AnthropicEvaluation code
    │
    └─ openai-cua:latest
        ├─ neurosim-base
        ├─ openai SDK
        ├─ playwright
        ├─ Chrome browser
        └─ OpenaiEvaluation code
```

#### CE Dockerfiles (Custom Branch Builds)

**Browser Use CE**: `CE/Dockerfile.browser_use`

Clones Browser Use from a specific branch/repo:

```dockerfile
FROM neurosim-base

ARG BROWSER_USE_BRANCH=main
ARG GH_TOKEN
ARG GH_REPO

# Clone browser-use from custom repo
# Install in editable mode
# Copy evaluation code
```

**Notte CE**: `CE/Dockerfile.notte`

Clones Notte from a specific branch:

```dockerfile
FROM neurosim-base

ARG NOTTE_BRANCH=main

# Clone notte
# Install in editable mode
# Copy evaluation code
```

### 5. Execution Flow

#### Single Task Execution

```
1. Container starts
   ↓
2. entrypoint.sh validates neurosim
   ↓
3. main.py CLI parsing
   ↓
4. EvaluationRequest created
   ↓
5. Agent initialization
   ↓
6. execute() orchestration
   │
   ├─ run() → Execute agent
   ├─ compute_steps() → Extract trajectory
   ├─ compute_tokens() → Track usage
   └─ save_results() → Upload to GCS
   ↓
7. Container exits
```

#### Multi-Episode Execution

Cloud Run jobs can run N parallel tasks (episodes):

```
Job: job_001 (3 episodes)
├─ Task 0 (CLOUD_RUN_TASK_INDEX=0)
├─ Task 1 (CLOUD_RUN_TASK_INDEX=1)
└─ Task 2 (CLOUD_RUN_TASK_INDEX=2)

Each task runs in its own container instance.
```

### 6. Result Format

**Storage Path**:
```
gs://bucket/{userid}/{jobid}/{episode}/{taskid}/
├── result.json.zst    (compressed result)
├── screenshot_1.png
├── screenshot_2.png
└── ...
```

**Result Structure** (`AgentResult`):
```json
{
  "jobId": "job_001",
  "success": true,
  "latency": 45.2,
  "tokens": [{
    "prompt_tokens": 1000,
    "completion_tokens": 500,
    "total_tokens": 1500
  }],
  "task": {
    "task": "Navigate to google.com",
    "taskId": "task_001",
    "model": "gpt-4o"
  },
  "steps": [{
    "action": "click",
    "element": "search_button",
    "screenshot": "gs://bucket/.../screenshot_1.png",
    "metadata": {...}
  }],
  "results": "Successfully navigated to google.com",
  "error": null
}
```

## Data Flow

### Development → Production

```
1. Code changes pushed to GitHub
   ↓
2. GitHub Actions triggered
   ↓
3. Docker images built
   ↓
4. Images pushed to Artifact Registry
   ↓
5. Cloud Run jobs use new images
   ↓
6. Results stored in GCS
   ↓
7. Judge evaluates results (optional)
```

### Continuous Evaluation Loop

```
1. Agent repo updated (Browser Use, Notte, etc.)
   ↓
2. Repository dispatch event sent
   ↓
3. GitHub Actions builds new image
   ↓
4. POST to CE platform API
   ↓
5. CE platform triggers Cloud Run job
   ↓
6. Job runs N episodes in parallel
   ↓
7. Results uploaded to GCS
   ↓
8. Firestore updated with completion status
   ↓
9. Judge evaluates results
   ↓
10. Metrics aggregated and displayed
```

## Configuration

### Environment Variables

See [ENV_VARIABLES.md](ENV_VARIABLES.md) for full list.

**Required**:
- `GCS_BUCKET_NAME`: GCS bucket for results
- `GOOGLE_APPLICATION_CREDENTIALS`: Service account key
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY`: LLM API keys

**Optional**:
- `GCP_PROJECT_ID`: GCP project
- `FIRESTORE_DATABASE`: Firestore database
- `LOG_LEVEL`: Logging level
- `ADVANCED_SETTINGS`: JSON config for agents

### GitHub Secrets

Required for CI/CD:
- `GCP_SA_KEY`: Service account JSON (base64 encoded)

## Performance Considerations

### Docker Build Optimization

1. **Layer caching**: System deps installed before app code
2. **Multi-stage builds**: Separate build and runtime stages (where applicable)
3. **GitHub Actions cache**: Use `cache-from`/`cache-to` for faster builds

### Execution Optimization

1. **Parallel episodes**: Cloud Run runs N tasks in parallel
2. **Isolated containers**: No state shared between episodes
3. **Headless browsers**: Faster execution without UI rendering
4. **Result compression**: 60-80% size reduction with zstd

## Security

### Credentials

- Service accounts with minimal permissions:
  - Storage Object Admin (GCS)
  - Artifact Registry Writer
  - Cloud Run Invoker (optional)
  - Firestore User (optional)

### Container Security

- Non-root user (where possible)
- Minimal base image (python:3.11-slim)
- No secrets in images (use env vars)
- Private container registry

### API Keys

- Loaded from environment at runtime
- Never committed to git
- Rotated regularly

## Troubleshooting

### Common Issues

1. **Build failures**: Check GCP authentication token
2. **Runtime failures**: Verify GCS bucket permissions
3. **Agent failures**: Check LLM API keys and quotas
4. **CI/CD failures**: Verify GitHub secrets and GCP service account

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
export DEBUG=true
```

### Local Testing

```bash
# Build base image
./neurosim-docker.sh

# Build agent image
cd BrowseruseEvaluation
docker build -t browser-use-test -f Dockerfile ..

# Run locally
docker run --rm \
    -e GCS_BUCKET_NAME=test \
    -e OPENAI_API_KEY=$OPENAI_API_KEY \
    -v ~/.config/gcloud:/root/.config/gcloud:ro \
    browser-use-test \
    python main.py --jobId test_001 ...
```

