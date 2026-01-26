# Use the official Python base image
FROM python:3.12-slim-bookworm

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Use a venv outside bind-mounted /app to avoid conflicts
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
# Force uv to use the container's Python instead of downloading one
ENV UV_PYTHON_PREFERENCE=only-system

# Copy lock files first for better Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into /opt/venv
RUN uv sync --frozen

# Now copy the rest of the project
COPY . .

# Ensure environment matches pyproject after full copy (installs any newly added deps like uvicorn)
RUN uv sync

# Set timezone
ENV TZ=Asia/Almaty
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
