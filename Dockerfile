FROM python:3.11-slim

# Install system deps required by some Python packages (kept minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Default command: use Gunicorn to serve the wsgi:app callable
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "wsgi:app"]
