# Using Python 3.11 slim as base image (more stable for ML deps)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements first
COPY backend/requirements.txt .

# Install CPU-optimized torch first to save space/time
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install the rest of the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code contents into /app
COPY backend/ .

# Ensure required state files exist or are initialized
RUN touch brain_state_ml.json brain_state.json rl_state.pt

# Environment variable for Hugging Face Default Port
ENV PORT=7860
EXPOSE 7860

# Run the FastAPI app using uvicorn
# We use log-level info to help user debug on HF console
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860", "--log-level", "info"]
