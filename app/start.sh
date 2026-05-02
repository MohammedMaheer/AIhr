#!/bin/bash

# Database connection configuration
echo "🔌 Database connection will be configured based on environment:"
echo "   🏠 Local: Direct TCP to your_db_host_ip:5432"
echo "   🌩️ Cloud Run: Unix socket via /cloudsql/your-gcp-project-id:me-central1:your-cloudsql-instance"

# Initialize background job system (simplified)
echo "Initializing background job system..."
python3 -c "
import sys
sys.path.append('/app')
try:
    from database import get_db_manager
    db = get_db_manager()
    db.initialize_background_jobs_table()
    print('✅ Background jobs system initialized')
except Exception as e:
    print(f'❌ Background jobs initialization failed: {e}')
    print('⚠️ Application will continue without background jobs')
" || echo "Background jobs initialization failed, continuing..."

# Start the FastAPI application with larger file upload limits
echo "Starting FastAPI application with background processing..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8080} \
    --workers ${WORKERS:-4} \
    --timeout-keep-alive 65 \
    --limit-max-requests 1000 \
    --limit-concurrency 100 \
    --loop asyncio \
    --log-level info 