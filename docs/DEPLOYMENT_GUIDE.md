# 🚀 Quick Deployment Guide

## Docker Local Development

1. **Clone the production branch**:
   ```bash
   git clone https://github.com/your-username/smarthr.git
   cd smarthr
   git checkout production
   ```

2. **Setup credentials**:
   ```bash
   # Place your GCP service account key as:
   cp /path/to/your/service-account.json ./service-account.json
   ```

3. **Start with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - URL: http://localhost:8000
   - Login: `admin@yourcompany.com` / `admin123`

## GCP Cloud Run Deployment

1. **Prerequisites**:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Deploy**:
   ```bash
   ./deploy/gcp-cloud-run.sh YOUR_PROJECT_ID us-central1
   ```

3. **Configure environment variables**:
   ```bash
   gcloud run services update hr-agent \
     --region=us-central1 \
     --set-env-vars="DB_HOST=YOUR_DB_HOST,DB_PASSWORD=YOUR_DB_PASSWORD"
   ```

## GKE Deployment

1. **Create cluster**:
   ```bash
   gcloud container clusters create hr-agent-cluster \
     --num-nodes=3 \
     --machine-type=e2-standard-2 \
     --region=us-central1
   ```

2. **Deploy**:
   ```bash
   # Update values in deploy/kubernetes/deployment.yaml
   kubectl apply -f deploy/kubernetes/deployment.yaml
   ```

## Environment Variables

Copy `env.example` to `.env` and update:
- Database connection details
- GCP project configuration
- Storage bucket names
- API keys and secrets

## Support

- 📧 Email: support@yourcompany.com
- 📖 Full README: See README.md for complete documentation 