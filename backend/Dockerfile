# Using Python 3.11 slim as base image
# Build Identifier: v9.9.9-INTEL-UPGRADE
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install PyTorch CPU-only (lightweight)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies
# Using --no-cache-dir to keep the image slim
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

# Environment variable for Hugging Face Default Port
ENV PORT=7860
EXPOSE 7860

# Run the FastAPI app using uvicorn
# We use 0.0.0.0 to bind to all interfaces
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]
