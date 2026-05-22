FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install required packages
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy server files. server.py is a thin shim that imports the gsheets_mcp
# package (which holds the tool modules and overrides the pip-installed upstream).
COPY gsheets_mcp /app/gsheets_mcp
COPY server.py /app/server.py
COPY entrypoint.py /app/entrypoint.py

# Expose ports
EXPOSE 8000 8001

# Health check on separate port
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application
CMD ["python", "/app/entrypoint.py"]
