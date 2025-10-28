.PHONY: build publish

build: 
	sudo DOCKER_BUILDKIT=1 docker build -t browseruse-eval .

publish:
	@echo "Pushing Docker image to repository..."
	sudo docker tag browseruse-eval:latest YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPO/browser-use:latest
	sudo docker push YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPO/browser-use:latest
	@echo "Docker image pushed"