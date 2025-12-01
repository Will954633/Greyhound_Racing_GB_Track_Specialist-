FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . .

# The models are already in artifacts/ directory and will be copied with COPY . .

# Expose port (Railway will set PORT env var)
ENV PORT=8080

# Run the worker process
CMD ["python", "run_continuous_scheduled.py", "--interval", "15", "--target", "1"]
