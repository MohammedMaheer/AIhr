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
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

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
