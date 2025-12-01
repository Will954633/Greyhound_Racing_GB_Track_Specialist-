FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Git LFS
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Initialize Git LFS
RUN git lfs install

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Download LFS files (this will replace pointer files with actual models)
RUN if [ -d .git ]; then \
        git lfs pull; \
    else \
        echo "Not a git repo, LFS files should already be present"; \
    fi

# Verify models exist and are large enough
RUN ls -lh artifacts/ && \
    test -f artifacts/base_model.cbm && \
    test -f artifacts/calibrator_model.cbm || \
    (echo "ERROR: Model files not found!" && exit 1)

# Expose port (Railway will set PORT env var)
ENV PORT=8080

# Run setup script then start the worker process
CMD python download_and_setup_models.py && python run_continuous_scheduled.py --interval 15 --target 1
