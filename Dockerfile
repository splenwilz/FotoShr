FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create upload directory
RUN mkdir -p app/static/uploads

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
# Environment variables for configuration will be passed at runtime

# Expose the port the app runs on
EXPOSE 5000

# Default command - will be overridden in devcontainer
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "5000"] 