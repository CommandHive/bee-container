# CommandHive Agent Base Image
FROM python:3.12.7-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    redis-server \
    supervisor \
    curl \
    git \
    build-essential \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*


# Create app directory structure
RUN mkdir -p /app/agents /app/logs /var/log/supervisor /etc/supervisor/conf.d

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY backend_server/templates/requirements.txt .
COPY backend_server/templates/sample_queen_agent.py .
COPY .env .

ADD https://astral.sh/uv/install.sh /uv-installer.sh

RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin/:$PATH"


RUN uv pip install --no-cache-dir -r requirements.txt --system

COPY templates/start.sh .
COPY templates/supervisord.conf /etc/supervisor/conf.d/supervisord.conf


# Create agents supervisor config directory
RUN mkdir -p /etc/supervisor/conf.d/agents

# Create a non-root user for security
RUN useradd -m -u 1000 agentuser && \
    chown -R agentuser:agentuser /app

# Expose port for agent communication and Redis
EXPOSE 8080 6379

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD redis-cli ping || exit 1

# Default command
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]