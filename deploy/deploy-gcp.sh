#!/bin/bash
# ==============================================================================
# SmartHR — One-Shot GCP Cloud Run Deployment
# ==============================================================================
# Usage:
#   bash deploy/deploy-gcp.sh [PROJECT_ID] [REGION]
#
# Example:
#   bash deploy/deploy-gcp.sh your-gcp-project-id us-central1
#
# Prerequisites:
#   - gcloud CLI installed and authenticated  (gcloud auth login)
#   - Docker installed and running
#   - psql installed locally (for schema migration)
#   - Service account JSON key: service-account.json
# ==============================================================================

set -e  # Exit immediately on any error

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
PROJECT_ID="${1:-your-gcp-project-id}"
REGION="${2:-us-central1}"
SERVICE_NAME="smarthr"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
CLOUD_SQL_INSTANCE="${SERVICE_NAME}-db"
CLOUD_SQL_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${CLOUD_SQL_INSTANCE}"
GCS_BUCKET_NAME="${PROJECT_ID}-resume-storage"
TASK_QUEUE_NAME="hr-scorecard-processing"
DB_NAME="${DB_NAME:-smarthr_db}"
DB_USER="${DB_USER:-smarthr_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"
MIN_INSTANCES=1
MAX_INSTANCES=10
MEMORY="2Gi"
CPU="2"
PORT=8080
SA_KEY_FILE="service-account.json"

# ─── COLORS ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[✓]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ─── PREFLIGHT CHECKS ─────────────────────────────────────────────────────────
echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│          SmartHR — One-Shot GCP Deployment                  │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""

command -v gcloud >/dev/null 2>&1 || error "gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install"
command -v docker  >/dev/null 2>&1 || error "Docker not found. Install Docker Desktop."

[ -f "${SA_KEY_FILE}" ] || error "Service account key not found: ${SA_KEY_FILE}"
[ -f "deploy/schema.sql" ]  || error "Schema file not found: deploy/schema.sql"

if [ -z "${DB_PASSWORD}" ]; then
  echo ""
  warn "DB_PASSWORD is not set. Please set it:"
  echo ""
  echo "  export DB_PASSWORD=your_secure_password"
  echo "  export DB_USER=smarthr_user      # optional, defaults to smarthr_user"
  echo "  export DB_NAME=smarthr_db        # optional, defaults to smarthr_db"
  echo ""
  read -rp "Enter DB_PASSWORD now: " DB_PASSWORD
  [[ -n "${DB_PASSWORD}" ]] || error "DB_PASSWORD cannot be empty."
fi

info "Project:    ${PROJECT_ID}"
info "Region:     ${REGION}"
info "Service:    ${SERVICE_NAME}"
info "Image:      ${IMAGE_NAME}"
info "Cloud SQL:  ${CLOUD_SQL_CONNECTION_NAME}"
info "GCS Bucket: ${GCS_BUCKET_NAME}"
info "Task Queue: ${TASK_QUEUE_NAME}"
echo ""

# ─── STEP 1: GCP Auth & Project Setup ────────────────────────────────────────
info "Step 1/11 — Setting active GCP project..."
gcloud config set project "${PROJECT_ID}"
success "Project set: ${PROJECT_ID}"

# ─── STEP 2: Enable Required APIs ────────────────────────────────────────────
info "Step 2/11 — Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  cloudtasks.googleapis.com \
  aiplatform.googleapis.com \
  discoveryengine.googleapis.com \
  storage.googleapis.com \
  --quiet
success "APIs enabled"

# ─── STEP 3: Provision Cloud SQL (PostgreSQL) ─────────────────────────────────
info "Step 3/11 — Provisioning Cloud SQL PostgreSQL instance..."
if gcloud sql instances describe "${CLOUD_SQL_INSTANCE}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  warn "Cloud SQL instance '${CLOUD_SQL_INSTANCE}' already exists — skipping creation."
else
  gcloud sql instances create "${CLOUD_SQL_INSTANCE}" \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region="${REGION}" \
    --storage-auto-increase \
    --backup-start-time=02:00 \
    --quiet
  success "Cloud SQL instance created: ${CLOUD_SQL_INSTANCE}"
fi

# Create DB and User
info "  Creating database '${DB_NAME}'..."
gcloud sql databases create "${DB_NAME}" \
  --instance="${CLOUD_SQL_INSTANCE}" \
  --quiet 2>/dev/null || warn "  Database '${DB_NAME}' may already exist — continuing."

info "  Creating database user '${DB_USER}'..."
gcloud sql users create "${DB_USER}" \
  --instance="${CLOUD_SQL_INSTANCE}" \
  --password="${DB_PASSWORD}" \
  --quiet 2>/dev/null || warn "  User '${DB_USER}' may already exist — continuing."

success "Cloud SQL database and user ready"

# ─── STEP 4: Run Schema Migrations via Cloud SQL Auth Proxy ──────────────────
info "Step 4/11 — Running database schema migrations..."

# Check if cloud-sql-proxy is available
if command -v cloud-sql-proxy >/dev/null 2>&1; then
  info "  Starting Cloud SQL Auth Proxy..."
  cloud-sql-proxy "${CLOUD_SQL_CONNECTION_NAME}" --port=5433 &
  PROXY_PID=$!
  sleep 5  # Wait for proxy to be ready

  info "  Applying schema (deploy/schema.sql)..."
  PGPASSWORD="${DB_PASSWORD}" psql \
    --host=127.0.0.1 \
    --port=5433 \
    --username="${DB_USER}" \
    --dbname="${DB_NAME}" \
    --file=deploy/schema.sql

  kill "${PROXY_PID}" 2>/dev/null || true
  success "Schema applied successfully"
else
  warn "cloud-sql-proxy not found — skipping local migration."
  warn "You can run it manually later:"
  warn "  cloud-sql-proxy ${CLOUD_SQL_CONNECTION_NAME} --port=5433 &"
  warn "  PGPASSWORD=\$DB_PASSWORD psql -h 127.0.0.1 -p 5433 -U ${DB_USER} -d ${DB_NAME} -f deploy/schema.sql"
fi

# ─── STEP 5: Create Google Cloud Storage Bucket ─────────────────────────────────
info "Step 5/11 — Provisioning Google Cloud Storage Bucket..."
if gcloud storage buckets describe "gs://${GCS_BUCKET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  warn "GCS Bucket '${GCS_BUCKET_NAME}' already exists — skipping creation."
else
  gcloud storage buckets create "gs://${GCS_BUCKET_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access \
    --quiet
  success "GCS Bucket created: ${GCS_BUCKET_NAME}"
fi

# ─── STEP 6: Create Cloud Tasks Queue ─────────────────────────────────────────
info "Step 6/11 — Provisioning Cloud Tasks Queue..."
if gcloud tasks queues describe "${TASK_QUEUE_NAME}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  warn "Cloud Tasks Queue '${TASK_QUEUE_NAME}' already exists — skipping creation."
else
  gcloud tasks queues create "${TASK_QUEUE_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --max-attempts=3 \
    --max-concurrent-dispatches=10 \
    --max-dispatches-per-second=5 \
    --quiet
  success "Cloud Tasks queue created: ${TASK_QUEUE_NAME}"
fi

# ─── STEP 7: Authenticate Docker with GCR ────────────────────────────────────
info "Step 7/11 — Authenticating Docker with Google Container Registry..."
gcloud auth configure-docker --quiet
success "Docker authenticated"

# ─── STEP 8: Build Docker Image ──────────────────────────────────────────────
info "Step 8/11 — Building Docker image..."
docker build \
  --platform linux/amd64 \
  -t "${IMAGE_NAME}:latest" \
  -t "${IMAGE_NAME}:$(git rev-parse --short HEAD 2>/dev/null || echo 'manual')" \
  .
success "Docker image built"

# ─── STEP 9: Push Docker Image to GCR ────────────────────────────────────────
info "Step 9/11 — Pushing image to Google Container Registry..."
docker push "${IMAGE_NAME}:latest"
success "Image pushed to GCR"

# ─── STEP 10: Upload SA Key to Secret Manager ─────────────────────────────────
info "Step 10/11 — Storing GCP credentials in Secret Manager..."
SECRET_NAME="smarthr-sa-key"
if ! gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud secrets create "${SECRET_NAME}" --replication-policy="automatic" --project="${PROJECT_ID}"
fi
gcloud secrets versions add "${SECRET_NAME}" --data-file="${SA_KEY_FILE}" --project="${PROJECT_ID}"
success "Credentials stored in Secret Manager"

# ─── STEP 11: Deploy to Cloud Run ─────────────────────────────────────────────
info "Step 11/11 — Deploying to Cloud Run..."
# Get the Cloud Run service URL for Cloud Tasks target_uri
SERVICE_URL_EXISTING=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format='value(status.url)' 2>/dev/null || echo "")

gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_NAME}:latest" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port "${PORT}" \
  --memory "${MEMORY}" \
  --cpu "${CPU}" \
  --min-instances "${MIN_INSTANCES}" \
  --max-instances "${MAX_INSTANCES}" \
  --timeout 300 \
  --concurrency 80 \
  --add-cloudsql-instances "${CLOUD_SQL_CONNECTION_NAME}" \
  --set-env-vars "\
CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONNECTION_NAME},\
DB_HOST=/cloudsql/${CLOUD_SQL_CONNECTION_NAME},\
DB_NAME=${DB_NAME},\
DB_USER=${DB_USER},\
DB_PASSWORD=${DB_PASSWORD},\
SECRET_KEY=${SECRET_KEY},\
GCP_PROJECT_ID=${PROJECT_ID},\
GCP_LOCATION=${REGION},\
GOOGLE_CLOUD_PROJECT=${PROJECT_ID},\
GCS_BUCKET_NAME=${GCS_BUCKET_NAME},\
DATASTORE_ID=${DATASTORE_ID:-},\
CLOUD_TASKS_QUEUE_NAME=${TASK_QUEUE_NAME},\
GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json,\
WORKERS=4" \
  --quiet

# ─── DONE ─────────────────────────────────────────────────────────────────────
echo ""
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format='value(status.url)')
echo "┌─────────────────────────────────────────────────────────────┐"
echo -e "│  ${GREEN}✅ Deployment Complete!${NC}                                     │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""
success "App URL:    ${SERVICE_URL}"
success "Health:     ${SERVICE_URL}/health"
success "Login:      admin@yourcompany.com / admin123"
echo ""
echo "Useful commands:"
echo "  gcloud run services describe ${SERVICE_NAME} --region=${REGION}"
echo "  gcloud beta run services logs tail ${SERVICE_NAME} --region=${REGION}"
echo "  gcloud sql connect ${CLOUD_SQL_INSTANCE} --user=${DB_USER}"
echo ""
