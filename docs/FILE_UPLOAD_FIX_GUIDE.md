# Fix for 413 "Content Too Large" Error

This guide explains how to fix the 413 error when uploading files to your Google Cloud Run deployment.

## Problem
The error `POST https://your-cloud-run-url.run.app/api/upload-files 413 (Content Too Large)` occurs because:

1. **Google Cloud Run Default Limits**: Cloud Run has a default 32MB request body size limit
2. **Your application advertises "unlimited size"** but the infrastructure has limits
3. **Files larger than 32MB** get rejected before reaching your FastAPI application

## Solutions Implemented

### 1. Application-Level Changes ✅

#### a) Added File Size Limits in FastAPI (`main.py`)
- **Client-side validation**: Files are checked before upload (100MB limit)
- **Server-side validation**: Double-checked when processing files
- **Better error messages**: Clear feedback about size limits

#### b) Updated JavaScript Client (`static/js/main.js`)
- **Pre-upload validation**: Files checked before being sent
- **Better error handling**: Specific messages for 413 errors
- **Updated UI text**: Changed from "unlimited size" to "max 100MB per file"

### 2. Infrastructure Changes ✅

#### a) Cloud Run Configuration (`deploy/gcp-cloud-run.sh`)
- **Increased memory**: 2Gi → 4Gi (handles larger files)
- **Increased CPU**: 2 cores → 4 cores (faster processing)
- **Extended timeout**: 15 min → 30 min (for large uploads)
- **Generation 2**: Uses newer Cloud Run generation with better limits

#### b) Uvicorn Configuration (`start.sh`)
- **Timeout settings**: Configured for longer connections
- **Concurrency limits**: Optimized for file uploads

## Deployment Instructions

### Option 1: Quick Deploy (Recommended)
```bash
# From your project root
chmod +x deploy/quick-deploy.sh
./deploy/quick-deploy.sh
```

### Option 2: Full Deploy with Cloud SQL
```bash
# Update project ID if needed
chmod +x deploy/gcp-cloud-run.sh
./deploy/gcp-cloud-run.sh your-project-id us-central1
```

### Option 3: Manual Deploy
```bash
# Build and push image
docker build -t gcr.io/your-project-id/hr-agent:latest .
docker push gcr.io/your-project-id/hr-agent:latest

# Deploy with new configuration
gcloud run deploy hr-agent \
    --image gcr.io/your-project-id/hr-agent:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --port 8080 \
    --memory 4Gi \
    --cpu 4 \
    --timeout 1800 \
    --execution-environment gen2 \
    --set-env-vars="PORT=8080"
```

## File Size Limits

| Component | Limit | Purpose |
|-----------|-------|---------|
| Client-side | 100MB | Pre-validation |
| Server-side | 100MB | Final validation |
| Cloud Run Gen2 | ~500MB* | Infrastructure limit |

*Cloud Run Gen2 supports larger requests but actual limit depends on memory allocation

## Testing the Fix

1. **Deploy the updated code** using one of the methods above
2. **Test with different file sizes**:
   - Small file (< 10MB) - should work
   - Medium file (10-50MB) - should work
   - Large file (50-100MB) - should work
   - Very large file (> 100MB) - should show clear error message

3. **Expected behavior**:
   - Files > 100MB: Blocked with clear error message
   - Files < 100MB: Upload successfully
   - No more 413 errors for reasonable file sizes

## Monitoring

After deployment, monitor your Cloud Run logs:
```bash
gcloud logs tail --follow \
    --filter="resource.type=cloud_run_revision AND resource.labels.service_name=hr-agent"
```

## Troubleshooting

### If you still get 413 errors:

1. **Check file size**: Ensure files are < 100MB
2. **Verify deployment**: Make sure new configuration is deployed
3. **Clear browser cache**: Hard refresh (Ctrl+Shift+R)
4. **Check Cloud Run settings**: Verify memory is 4Gi and execution-environment is gen2

### If upload is slow:

1. **Check network**: Large files take time to upload
2. **Monitor progress**: UI shows upload progress
3. **Be patient**: 100MB files can take several minutes on slow connections

## Security Notes

- File type validation remains in place (PDF, DOC, DOCX only)
- Company isolation is maintained (files go to company-specific buckets)
- User authentication required for all uploads
- Resume count limits still apply per company

## Rollback (if needed)

If something goes wrong, you can rollback:
```bash
gcloud run services replace-traffic hr-agent --to-revisions=PREVIOUS_REVISION=100
```

Replace `PREVIOUS_REVISION` with the previous working revision ID.

---

**Status**: ✅ **IMPLEMENTED** - Ready for deployment
**Next**: Deploy using one of the methods above and test file uploads 