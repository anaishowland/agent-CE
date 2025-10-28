.PHONY: build publish

build: 
	sudo DOCKER_BUILDKIT=1 docker build -t browseruse-eval .

publish:
	@echo "Pushing Docker image to repository..."
	sudo docker tag browseruse-eval:latest us-central1-docker.pkg.dev/evaluation-deployment/agents/browser-use:latest
	sudo docker push us-central1-docker.pkg.dev/evaluation-deployment/agents/browser-use:latest
	@echo "Docker image pushed"