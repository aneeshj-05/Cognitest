# Use a Python image with uv pre-installed for faster builds
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Set the working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy project files for dependency installation
# Copy uv.lock and pyproject.toml if they exist
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
# --frozen ensures we use the exact versions from uv.lock
# --no-install-project skips installing the current project itself in this step
RUN uv sync --frozen --no-install-project --no-dev

# Final Stage
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy the environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Ensure we use the virtualenv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Install libpq and libatomic for PostgreSQL and Prisma
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code
COPY . .

# Generate Prisma client
RUN prisma generate

# ---------------------------------------------------------------------------
# Create a dedicated non‑root user and give it ownership of runtime paths
# ---------------------------------------------------------------------------
# The builder stage runs as root (default).  We create a low‑privilege user,
# make the application directory and the logs sub‑directory owned by that user,
# and then switch to it for the runtime container.
RUN useradd -ms /bin/bash appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app/logs

# Run the container as the non‑root user
USER appuser

# Expose the port the app runs on
EXPOSE 5000

# Run the application
# Using src.main:app because main.py is inside src/
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000"]
