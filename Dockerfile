# --- Stage 1: Build Frontend ---
FROM node:18-alpine AS build-stage
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Final Production Image ---
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install aiofiles

# Copy the rest of the application
COPY . .

# Copy built frontend from build-stage
COPY --from=build-stage /app/frontend/dist ./frontend/dist

# Expose Hugging Face default port
EXPOSE 7860

# Force environment to recognize modules
ENV PYTHONPATH=/app

# Command to run the unified server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
