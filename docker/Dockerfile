# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install paho-mqtt

# Expose ports
EXPOSE 5000
EXPOSE 5001

# Command to run the app
CMD ["python", "main.py"]