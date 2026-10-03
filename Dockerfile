FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml .

# Install dependencies into system environment
RUN uv pip install --system -e .

# Copy application source code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.service:app", "--host", "0.0.0.0", "--port", "8000"]
