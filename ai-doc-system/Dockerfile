FROM python:3.11-slim

# Install system dependencies: git, nodejs, npm, and chromium (required for headless mmdc)
RUN apt-get update && apt-get install -y \
    git \
    nodejs \
    npm \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Install mermaid-cli globally
RUN npm install -g @mermaid-js/mermaid-cli

# Tell Puppeteer (used by mmdc) where to find the system chromium
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Set the working directory
WORKDIR /app

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose default port
EXPOSE 8000

# Start FastAPI application
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
