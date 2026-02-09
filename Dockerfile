# Build Identifier: v12.6.2-FINAL-PROD
FROM python:3.12-slim

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

# Ensure required state files exist or are initialized without overwriting
RUN [ ! -f brain_state_ml.json ] && touch brain_state_ml.json || true
RUN [ ! -f brain_state.json ] && touch brain_state.json || true
RUN [ ! -f rl_state.pt ] && touch rl_state.pt || true

# Environment variable for Hugging Face Default Port
ENV PORT=7860
EXPOSE 7860

# [v9.9.6] Stability: Limit threads to prevent container eviction
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1

# Run the FastAPI app using uvicorn
# We use --workers 1 to minimize memory footprint
CMD uvicorn api:app --host 0.0.0.0 --port $PORT --log-level info --workers 1
