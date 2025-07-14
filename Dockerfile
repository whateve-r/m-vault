# Base image
FROM python:3.11-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (use Docker caching)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy rest of the project
COPY . /app

# Create non-root user and set permissions
RUN adduser -u 5678 --disabled-password --gecos "" appuser && \
    chown -R appuser /app
USER appuser

# Default command
CMD ["python", "bot/main.py"]
