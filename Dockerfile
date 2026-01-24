FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openssh-client \
    curl \
    git \
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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directories for logs and data
RUN mkdir -p logs data

CMD ["python", "main.py"]
