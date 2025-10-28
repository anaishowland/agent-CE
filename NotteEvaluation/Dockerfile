# Dockerfile for Notte Evaluation
FROM neurosim-base

ENV PYTHONUNBUFFERED=1
ENV NOTTE_CONFIG_PATH=/app/NotteEvaluation/notte_config.toml
ENV GOOGLE_CLOUD_PROJECT=YOUR_GCP_PROJECT_ID

RUN uv pip install --system notte
RUN python -m patchright install chrome

# Copy application code
COPY . /app/NotteEvaluation
WORKDIR /app

# Verify neurosim is still available after app installation
RUN python -c "import neurosim; print('neurosim verified in final notte-eval image')"

RUN chmod +x ./NotteEvaluation/entry.sh

ENTRYPOINT ["./NotteEvaluation/entry.sh"]