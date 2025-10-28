# Contributing to Agent-CE

Thank you for your interest in contributing to Agent-CE! This project provides a continuous evaluation platform for web browsing agents.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Adding a New Agent](#adding-a-new-agent)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Pull Request Process](#pull-request-process)
- [Code of Conduct](#code-of-conduct)

## Prerequisites

- **Python 3.11+** (required)
- **Docker** (for building and testing containers)
- **Git** (required)
- **Google Cloud SDK** (optional, for GCS integration)
- **neurosim package** (dependency) - See [neurosim repo](https://github.com/anaishowland/neurosim)

## Development Setup

### 1. Clone Repositories

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

### 2. Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install agent dependencies
pip install browser-use notte playwright anthropic openai

# Install Playwright browsers
playwright install chrome
```

### 3. Set Up Environment

Create a `.env` file (see [ENV_VARIABLES.md](ENV_VARIABLES.md) for all options):

```bash
# Required
GCS_BUCKET_NAME=your-test-bucket
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
OPENAI_API_KEY=your_key

# Optional
LOG_LEVEL=DEBUG
```

### 4. Verify Setup

```bash
# Test Browser Use agent
cd BrowseruseEvaluation
python main.py \
    --jobId test_001 \
    --task "Open google.com" \
    --taskId task_001 \
    --user dev \
    --episode 0 \
    --model gpt-4o
```

## Project Structure

```
agent-CE/
├── BrowseruseEvaluation/     # Browser Use agent implementation
│   ├── main.py               # Main evaluation class
│   ├── llm.py                # LLM configuration
│   ├── Dockerfile            # Container definition
│   ├── requirements.txt      # Dependencies
│   ├── entry.sh              # Entrypoint script
│   └── Makefile              # Build automation
├── NotteEvaluation/          # Notte agent implementation
│   └── ...                   # Similar structure
├── AnthropicEvaluation/      # Anthropic Computer Use
│   └── ...
├── OpenaiEvaluation/         # OpenAI Computer Use
│   └── ...
├── CE/                       # Continuous Evaluation Dockerfiles
│   ├── Dockerfile.browser_use
│   └── Dockerfile.notte
├── .github/
│   ├── workflows/            # CI/CD pipelines
│   └── actions/              # Custom GitHub Actions
├── Dockerfile.base           # Base image with neurosim
├── entrypoint.sh             # Base entrypoint
└── neurosim-docker.sh        # Base image build script
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Your Changes

- Follow existing code patterns and structure
- Add docstrings for new classes and methods
- Use type hints
- Update documentation as needed

### 3. Test Locally

```bash
# Test Python code directly
cd BrowseruseEvaluation
python main.py --jobId test ...

# Test with Docker
docker build -t test-agent -f Dockerfile .
docker run --rm -e GCS_BUCKET_NAME=test test-agent python main.py ...
```

### 4. Code Quality Checks

```bash
# Format code (if you have black installed)
black BrowseruseEvaluation/ NotteEvaluation/ AnthropicEvaluation/ OpenaiEvaluation/

# Sort imports (if you have isort installed)
isort BrowseruseEvaluation/ NotteEvaluation/ AnthropicEvaluation/ OpenaiEvaluation/

# Type checking (if you have mypy installed)
mypy BrowseruseEvaluation/main.py
```

### 5. Commit and Push

```bash
git add .
git commit -m "feat: add new agent feature"
git push origin feat/your-feature-name
```

### 6. Open a Pull Request

- Provide a clear description of changes
- Reference any related issues
- Include testing instructions
- Wait for review and address feedback

## Adding a New Agent

To add a new agent implementation:

### 1. Create Agent Directory

```bash
mkdir YourAgentEvaluation
cd YourAgentEvaluation
```

### 2. Implement Evaluation Class

Create `main.py`:

```python
"""YourAgent Evaluation Module"""
import logging
from neurosim.evaluation import Evaluation
from neurosim.utils.models import EvaluationRequest, AgentResult

logger = logging.getLogger(__name__)

class YourAgentEvaluation(Evaluation):
    def __init__(self, request: EvaluationRequest):
        super().__init__(request)
        self.agent_name = "YourAgent"
        self.agent_version = "1.0.0"
    
    def get_llm(self):
        """Return the LLM configuration"""
        return "gpt-4o"  # or your LLM config
    
    async def run(self) -> AgentResult:
        """Execute the agent task"""
        try:
            # Implement your agent logic here
            # 1. Initialize agent
            # 2. Run the task
            # 3. Collect results
            
            self.result.success = True
            self.result.results = "Task completed"
        except Exception as e:
            self.result.error = AgentErrors(
                name="AgentError",
                traceback=traceback.format_exc(),
                error=str(e)
            )
        return self.result
    
    def compute_steps(self):
        """Process agent steps/trajectory"""
        self.result.steps = []
        # Extract and save screenshots, steps, etc.
    
    def compute_tokens(self):
        """Calculate token usage"""
        self.result.tokens = []
        # Extract token usage from agent

if __name__ == "__main__":
    import asyncio
    eval_instance = YourAgentEvaluation.from_cli()
    asyncio.run(eval_instance.execute())
```

### 3. Create Dockerfile

Create `Dockerfile`:

```dockerfile
FROM neurosim-base

ENV PYTHONUNBUFFERED=1

# Install agent-specific dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Add required system packages \
    && rm -rf /var/lib/apt/lists/*

# Install agent Python package
RUN uv pip install --system your-agent-package

# Copy application code
COPY . /app/YourAgentEvaluation
WORKDIR /app

RUN chmod +x ./YourAgentEvaluation/entry.sh

ENTRYPOINT ["./YourAgentEvaluation/entry.sh"]
```

### 4. Create Entry Script

Create `entry.sh`:

```bash
#!/bin/bash
set -e

# Verify neurosim is available
if python -c "import neurosim" 2>/dev/null; then
    echo "[INFO] neurosim package is available"
else
    echo "[ERROR] neurosim package not found"
    exit 1
fi

# Execute the command
exec "$@"
```

Make it executable:

```bash
chmod +x entry.sh
```

### 5. Add Requirements

Create `requirements.txt`:

```
your-agent-package
# Additional dependencies
```

### 6. Update CI/CD

Add your agent to `.github/workflows/docker-build.yml`:

```yaml
strategy:
  matrix:
    include:
      # ... existing agents ...
      - name: your-agent
        dir: YourAgentEvaluation
        dockerfile: YourAgentEvaluation/Dockerfile
```

### 7. Test Your Agent

```bash
# Build base image first
./neurosim-docker.sh

# Build your agent image
cd YourAgentEvaluation
docker build -t your-agent-eval -f Dockerfile ..

# Test it
docker run --rm \
    -e GCS_BUCKET_NAME=test-bucket \
    -e OPENAI_API_KEY=your_key \
    your-agent-eval \
    python main.py --jobId test_001 --task "..." --taskId task_001 --user dev --episode 0
```

## Testing

### Unit Testing

```python
# tests/test_your_agent.py
import pytest
from YourAgentEvaluation.main import YourAgentEvaluation
from neurosim.utils.models import EvaluationRequest

def test_agent_initialization():
    request = EvaluationRequest(
        userid="test",
        model="gpt-4o",
        jobid="job_001",
        task="test task",
        taskid="task_001",
        browser_channel="chrome",
        episode=0,
        advanced_settings={},
        bucket_name="test-bucket"
    )
    agent = YourAgentEvaluation(request)
    assert agent.agent_name == "YourAgent"
```

### Integration Testing

Test the full Docker workflow:

```bash
# Build and run with Docker Compose (if configured)
docker-compose up your-agent

# Or manually
./test-agent-docker.sh YourAgent
```

## Code Quality

### Style Guidelines

- Use **type hints** for all function parameters and returns
- Add **docstrings** (Google style) for all public classes and methods
- Keep functions **small and focused** (< 50 lines ideally)
- Use **descriptive variable names**
- Handle errors explicitly with proper exception types

### Example Good Code

```python
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def process_task(
    task_description: str,
    max_steps: int = 50
) -> Optional[dict]:
    """
    Process an evaluation task using the agent.
    
    Args:
        task_description: Natural language task description
        max_steps: Maximum steps the agent can take
        
    Returns:
        Result dictionary with success status and details,
        or None if processing failed
        
    Raises:
        ValueError: If task_description is empty
        RuntimeError: If agent initialization fails
    """
    if not task_description:
        raise ValueError("Task description cannot be empty")
    
    logger.info("Processing task: %s", task_description[:50])
    
    # Implementation...
    return {"success": True, "result": "..."}
```

### Avoid

- Broad `except Exception:` without reraising or logging
- Magic numbers (use constants)
- Deep nesting (> 3 levels)
- Global state
- Tight coupling to specific implementations

## Pull Request Process

1. **Update Documentation**: Update README.md, ENV_VARIABLES.md if needed
2. **Add Tests**: Include tests for new features
3. **Keep PRs Small**: Focus on one feature/fix per PR
4. **Write Clear Commit Messages**:
   - `feat: add Notte agent integration`
   - `fix: resolve screenshot capture bug`
   - `docs: update setup instructions`
4. **Update CHANGELOG**: Add entry to CHANGELOG.md (if it exists)
5. **Request Review**: Tag relevant reviewers

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Testing
- [ ] Tested locally
- [ ] Tested with Docker
- [ ] Added unit tests
- [ ] Tested integration with neurosim

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No new warnings or errors
- [ ] All tests pass
```

## Code of Conduct

This project adheres to the Contributor Covenant [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Help

- **Documentation**: Check [README.md](README.md) and [ENV_VARIABLES.md](ENV_VARIABLES.md)
- **Issues**: Search [existing issues](https://github.com/anaishowland/agent-CE/issues)
- **Discussions**: Join [discussions](https://github.com/anaishowland/agent-CE/discussions)
- **Email**: For sensitive issues, contact anaisaddad@gmail.com

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Agent-CE! Your contributions help make this project better for everyone.

