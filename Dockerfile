# Use a base image with Python and build tools
FROM python:3.10-slim

# Install system dependencies for dlib
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libboost-all-dev \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy your code
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r backend/requirements.txt

# Expose port (adjust if needed)
EXPOSE 5000

# Start your Flask app
CMD ["gunicorn", "--chdir", "backend", "app:app", "--bind", "0.0.0.0:5000"]
