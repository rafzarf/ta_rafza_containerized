# Stage 1: Install dependencies in a build environment
FROM python:3.9-slim AS builder

WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and templates to the build environment
COPY app /app

# Stage 2: Create the final image with only the necessary files and packages
FROM python:3.9-slim

WORKDIR /app

# Copy dependencies and application code from the builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /app /app

# Expose necessary port for Flask
EXPOSE 5000

# Run the Flask application
CMD ["python", "app/model_deployment/main_app.py"]
