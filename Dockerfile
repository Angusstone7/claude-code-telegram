FROM python:3.11-slim

# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y \
    openssh-client \
    curl \
    git \
    ca-certificates \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Clone official Claude Code plugins
# The repo structure is: /plugins-repo/plugins/<plugin-name>/
# We need plugins accessible at /plugins/<plugin-name>/
RUN git clone --depth 1 https://github.com/anthropics/claude-plugins-official.git /plugins-repo && \
    mv /plugins-repo/plugins /plugins && \
    rm -rf /plugins-repo

WORKDIR /app

# Cache bust argument - changes with each commit
ARG CACHE_BUST=1
RUN echo "Cache bust: $CACHE_BUST"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Debug: verify keyboards.py has proxy methods
RUN grep -n "proxy_settings_menu" presentation/keyboards/keyboards.py || echo "ERROR: proxy_settings_menu not found!"

# Build Telegram MCP server
WORKDIR /app/telegram-mcp
RUN npm install && npm run build

WORKDIR /app

# Create directories for logs and data
RUN mkdir -p logs data

# Disable bytecode caching to prevent stale .pyc issues
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Prometheus metrics endpoint
EXPOSE 9090

CMD ["python", "main.py"]
