# Use a lightweight Python image
FROM python:3.11-slim

# Install system dependencies for aiortc
RUN apt-get update && apt-get install -y \
    gcc \
    libavdevice-dev \
    libavfilter-dev \
    libopus-dev \
    libvpx-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app and static files
COPY app.py .
COPY static/ ./static/

# Expose the web port
EXPOSE 8080

# Run the app
CMD ["python", "app.py"]
