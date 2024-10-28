# Dockerfile

# Stage 1: Build dependencies in a minimal base
FROM python:3.9-slim AS builder

WORKDIR /app

# Install dependencies without caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir paho-mqtt flask-mqtt

# Copy application code
COPY app /app

# Stage 2: Create the final image with only the necessary files
FROM python:3.9-slim

WORKDIR /app

# Copy dependencies and application code from builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /app /app

# Expose necessary ports (for Flask app)
EXPOSE 5000
EXPOSE 5001
