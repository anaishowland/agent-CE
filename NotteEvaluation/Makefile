.PHONY: setup venv install clean help docker-push

build:
	@echo "Building Docker image..."
	sudo DOCKER_BUILDKIT=1 docker build -t notte-eval .

# Setup virtual environment and install all dependencies
setup: venv install

# Create virtual environment
venv:
	uv venv .venv
	@echo "Virtual environment created at .venv"

publish:
	@echo "Pushing Docker image to repository..."
	sudo docker tag notte-eval:latest us-central1-docker.pkg.dev/evaluation-deployment/agents/notte:latest
	sudo docker push us-central1-docker.pkg.dev/evaluation-deployment/agents/notte:latest
	@echo "Docker image pushed"

# Install production dependencies
install:
	@echo "Installing production dependencies..."
	@echo "Installing private packages from private repository..."
	uv pip install --upgrade --extra-index-url=https://oauth2accesstoken:$(shell gcloud auth print-access-token)@us-west1-python.pkg.dev/evaluation-deployment/neuro-deploy/simple/ -r requirements-private.txt
	@echo "Installing public production dependencies..."
	uv pip install -r requirements.txt
	@echo "Production dependencies installed"

# Clean up
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	@echo "Cleanup completed"
	rm -rf .venv
	@echo "Virtual environment removed"

# Load environment variables from .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Help
help:
	@echo "Available commands:"
	@echo "  setup-script   - Run interactive setup script (recommended for new users)"
	@echo "  setup          - Setup virtual environment and install all dependencies"
	@echo "  venv           - Create virtual environment"
	@echo "  install        - Install production dependencies (private + public)"
	@echo "  help           - Show this help message"
	@echo ""
	@echo "Environment:"
	@echo "  .env file will be automatically loaded if present"
	@echo "  neurosim will be installed from private repository using gcloud auth"
