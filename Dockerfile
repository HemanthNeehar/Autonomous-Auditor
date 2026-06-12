FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY . .

# Set environment variables for production/local fallback
ENV PORT=8080
ENV DB_MODE=local
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE

# Expose Cloud Run port
EXPOSE 8080

# Run FastAPI application via uvicorn
CMD ["sh", "-c", "uvicorn ui.app:app --host 0.0.0.0 --port ${PORT}"]