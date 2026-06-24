# Stage 1: Builder
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
COPY requirements-vps.txt ./
ARG INSTALL_VPS_DEPS=0
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_VPS_DEPS" = "1" ]; then \
        pip install --prefix=/install --no-cache-dir -r requirements-vps.txt ; \
    fi

# Stage 1b: CSS builder (Tailwind standalone CLI, no Node needed)
FROM debian:bookworm-slim AS css-builder
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates wget \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /css
RUN wget -qO tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.13/tailwindcss-linux-x64 \
    && chmod +x tailwindcss
COPY tailwind.config.js tailwind.input.css ./
COPY templates ./templates
COPY static ./static
RUN ./tailwindcss -c tailwind.config.js -i tailwind.input.css -o /css/tailwind.css --minify

# Stage 2: Runtime
FROM python:3.11-slim

# Install runtime dependencies (e.g., libpq5 if using PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Cloud SQL Proxy
RUN wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O cloud_sql_proxy && \
    chmod +x cloud_sql_proxy && \
    mv cloud_sql_proxy /usr/local/bin/

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy installed Python packages
COPY --from=builder /install /usr/local

# Set working directory
WORKDIR /app

# Copy your FastAPI app
COPY . .

# Copy built Tailwind CSS bundle from the css-builder stage
COPY --from=css-builder /css/tailwind.css /app/static/css/tailwind.css

# Create logs/uploads directories
RUN mkdir -p /app/logs /app/uploads

# Make startup script executable and set ownership
RUN chmod +x start.sh && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Ensure PATH includes user-installed packages
ENV PATH="/usr/local/bin:$PATH"

# Expose the port Cloud Run uses
EXPOSE $PORT

# Optional health check (Cloud Run uses internal probes)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl --fail http://localhost:$PORT/health || exit 1

# Start FastAPI app
CMD ["./start.sh"]
