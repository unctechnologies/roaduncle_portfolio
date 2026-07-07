# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Prevent Python from buffering stdout and stderr (Crucial for streaming logs in Docker)
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Copy the knowledge base directory requirements
COPY mvl_data.txt /app/mvl_data.txt
COPY soul.md /app/soul.md

# Copy your new Telegram bot code (renamed to match your original main.py structure)
COPY bot.py /app/bot.py

# Copy the requirements file
COPY requirements.txt /app/requirements.txt

# Install any needed packages (Ensure python-telegram-bot and google-generativeai are listed here)
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user and group for production hardening
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Change ownership of /app so the non-root user can read/write files like interactions.md
RUN chown -R appuser:appgroup /app

USER appuser

# Define default environment variables
ENV GEMINI_MODEL="gemini-2.5-flash"

# Run the Telegram bot directly using Python
CMD ["python", "bot.py"]
