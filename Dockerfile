FROM python:3.10-slim

# Set environment variables to avoid python generating .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies (ffmpeg is required for Whisper, git for installing Whisper from GitHub)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Ensure storage directories exist in the container
RUN mkdir -p /root/ai_interview_simulator_data/tts_audio

# Expose port
EXPOSE 8000

# Start the FastAPI application via uvicorn
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
