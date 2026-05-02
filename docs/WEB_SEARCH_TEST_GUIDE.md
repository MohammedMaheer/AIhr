# Web Search Test Guide

## Overview
This guide explains how to test the GCP Web Search functionality using Vertex AI Search integration.

## Test Scripts Available

### 1. `quick_web_search_test.py` - Quick Test
A lightweight script for fast testing.

**Usage:**
```bash
python quick_web_search_test.py
```

**What it tests:**
- Configuration loading
- Web search setup
- Basic search functionality with Google and Microsoft

### 2. `test_gcp_web_search_comprehensive.py` - Comprehensive Test
A thorough test suite with detailed reporting.

**Usage:**
```bash
python test_gcp_web_search_comprehensive.py
```

**What it tests:**
- Configuration validation
- Module imports
- GCP client connection
- Basic search functionality
- Multiple search queries
- Performance metrics

### 3. `test_web_search.py` - Existing Test (Already in your project)
The original test script with JD generation testing.

## Prerequisites

### 1. Vector Search Setup
The web search functionality now uses your existing Discovery Engine setup. Make sure your `config.json` has the `vector_search` section properly configured. No separate web search app is needed.

### 2. Required Dependencies
Make sure you have these installed:

```bash
pip install google-cloud-discoveryengine
pip install google-cloud-storage
pip install google-genai
```

### 3. GCP Authentication
Ensure your GCP credentials are properly configured:

```bash
# Using service account key
export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service-account-key.json"

# OR using gcloud auth
gcloud auth application-default login
```

### 4. Required APIs
Enable these GCP APIs in your project:
- Discovery Engine API
- Vertex AI API
- Search API

## Expected Configuration

Your `config.json` should include a `vector_search` section like this:

```json
{
  "vector_search": {
    "project_id": "your-project-id",
    "location": "global",
    "datastore_id": "your-resume-datastore-id"
  }
}
```

The web search will use your existing resume search engine with enhanced web search capabilities.

## Test Results Interpretation

### ✅ Success Indicators
- Configuration loads successfully
- All required modules import
- GCP client connects
- Search queries return meaningful results
- Response times are reasonable (< 10 seconds)

### ❌ Common Issues

**1. "Vector search not configured"**
- Solution: Check that your `config.json` has the `vector_search` section with required fields

**2. "Failed to import Google Cloud modules"**
- Solution: Install required packages: `pip install google-cloud-discoveryengine`

**3. "Client connection failed"**
- Solution: Check GCP authentication and API enablement

**4. "Search returned empty result"**
- Solution: Check if your search app has been properly indexed (may take time)

### ⚠️ Warnings
- "Search result may not be relevant" - Results don't contain query term
- "Empty or minimal result" - Search returned very short results

## Troubleshooting

### 1. Check GCP Project Setup
```bash
gcloud config get-value project
gcloud auth list
```

### 2. Verify API Enablement
```bash
gcloud services list --enabled | grep discovery
gcloud services list --enabled | grep aiplatform
```

### 3. Test Basic Connectivity
```bash
# Test if you can access GCP APIs
python -c "from google.cloud import discoveryengine_v1; print('OK')"
```

### 4. Manual Search Test
```python
from main import search_web_for_company_info
result = search_web_for_company_info("Google")
print(f"Result: {result}")
```

## Performance Expectations

- **Setup Time**: Initial web search app creation takes 5-15 minutes
- **Search Time**: Individual searches should complete in 2-10 seconds
- **Success Rate**: Expect 80%+ success rate for well-known companies
- **Result Quality**: Results should contain relevant company information

## Usage in Production

Once tests pass, you can use the web search functionality in your main application:

1. **JD Builder**: Automatically fetch company information
2. **API Endpoints**: Use `/api/generate-jd` with company names
3. **Direct Function**: Call `search_web_for_company_info(company_name)` directly

## Monitoring

- Monitor search performance and success rates
- Check GCP quotas and usage
- Review search quality periodically
- Update search configurations as needed

## Support

If tests fail consistently:

1. Check this guide's troubleshooting section
2. Review GCP console for error messages
3. Verify billing account is active
4. Check regional availability of Vertex AI Search
5. Ensure your Discovery Engine datastore has web search capabilities enabled

---

**Note:** Web search functionality requires active GCP billing account and may incur costs based on usage. 