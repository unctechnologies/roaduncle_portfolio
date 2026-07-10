# Use an official Python runtime as a parent image
FROM python:3.11-slim-bookworm

# Prevent Python from buffering stdout and stderr (Crucial for streaming logs in Docker)
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required to build packages like numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the knowledge base directory requirements
COPY mvl_data.json /app/mvl_data.json
COPY soul.md /app/soul.md

# Copy your new Telegram bot code (renamed to match your original main.py structure)
COPY bot.py /app/bot.py

# Create a non-root user and group for production hardening
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Change ownership of /app so the non-root user can read/write files like interactions.md
RUN chown -R appuser:appgroup /app

USER appuser

# Define default environment variables
ENV GEMINI_MODEL="gemini-2.5-flash"

# Run the Telegram bot directly using Python
CMD ["python", "bot.py"]
