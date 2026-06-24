#!/bin/bash
set -e

echo "Database connection will be configured based on environment:"
echo "   Local: Direct TCP using DB_HOST/DB_PORT"
echo "   Cloud Run: Unix socket via CLOUD_SQL_CONNECTION_NAME"

echo "Starting FastAPI application..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8080} \
    --workers ${WORKERS:-4} \
    --timeout-keep-alive 65 \
    --limit-max-requests 1000 \
    --limit-concurrency ${UVICORN_LIMIT_CONCURRENCY:-100} \
    --loop asyncio \
    --log-level info
