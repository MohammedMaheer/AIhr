# Codester Listing Information

Use the information below to fill out the Codester product creation form.

---

### Name
*(Maximum 50 characters)*
**SmartHR - AI Recruitment & ATS Platform**  *(41 characters)*
*Alternative:* **Smart HR: AI Resume Search & Scorecard API** *(44 characters)*

---

### Short description
*(Maximum 130 characters)*
**Enterprise-grade AI recruitment platform powered by Google Gemini. Features semantic resume search, AI scorecards, and a full ATS.** *(128 characters)*

---

### Description
**Smart HR** is a production-ready, enterprise-grade AI recruitment platform and Applicant Tracking System (ATS). It allows HR professionals to instantly generate professional Job Descriptions from scratch using AI, upload candidate resumes (PDF/DOCX), let Google's advanced **Gemini 2.5 Flash AI** analyze them, and instantly find the best matches. 

The application architecture includes a powerful FastAPI backend, a responsive Vanilla JS and TailwindCSS frontend dashboard, and robust integrations with **Google Cloud Platform** (Cloud Run, Cloud Storage, Vertex AI, Discovery Engine, and Cloud Tasks).

It supports full **multi-tenant** data isolation, allowing you to run this software for multiple companies simultaneously, with subscription limits and separate storage buckets for each.

The codebase is highly optimized, fully documented, and includes a **one-click GCP deployment script** that entirely provisions your cloud infrastructure automatically.

---

### Features
*   **Batch Intelligent Document Processing:** Drag-and-drop PDF and DOCX resume parsing (up to 100MB per file) via `pdfplumber` and `PyPDF2`.
*   **AI-Powered HR Scorecards:** Gemini generates detailed candidate evaluations including an overall match score (0-100%), skill keyword matching, and experience fit analysis.
*   **Semantic Candidate Search:** Google Discovery Engine performs advanced vector similarity search across all indexed resumes in real-time.
*   **AI Job Description Generator:** Generate complete, professional JDs from scratch, enhance existing drafts, and automatically extract required searchable keywords.
*   **Multi-Tenant Architecture:** Built-in segregation of duties for Super Admins, Company Admins, and HR Users, with isolated storage and database rows per tenant.
*   **Candidate Pipeline Management:** Manage candidate workflows (shortlist, reject, interview scheduling, hire).
*   **Background Processing:** Scalable Cloud Tasks integration ensures the UI remains fast during heavy batch processing.
*   **Enterprise Security:** `bcrypt`-hashed passwords, secure cookie sessions, 413 file upload middleware limits, and full JSONB audit logging of all sensitive actions.
*   **Automated Cloud Deployment:** Includes a single bash script that automatically provisions Cloud SQL, GCS, Cloud Tasks, Secret Manager, and deploys to Cloud Run.

---

### Requirements
*   **Backend:** Python 3.11+
*   **Database:** PostgreSQL 15+
*   **Cloud Provider:** Google Cloud Platform (Billing enabled)
*   *Optional but Recommended:* Docker & Docker Compose for local development

---

### Instructions
**Getting Started & Deployment**

The codebase includes two comprehensive guides:
1.  **`README.md`**: Provides a high-level overview of the technology stack, application modules, and exact database schemas.
2.  **`deploy/README.md`**: Contains step-by-step, heavily detailed instructions with commands on how to set up your Google Cloud account and deploy the application.

**Quick Deploy (GCP):**
We have included a `deploy-gcp.sh` script that automates the entire infrastructure setup for you. Just set your database variables and run a single command to push your app to Cloud Run automatically!

*(Optional: Add a link to your YouTube Demo Video here if you upload one)*

---

### Development time (hours)
**250**
*(The codebase contains ~10,000 lines of complex Python logic, cloud integrations, database schema management, and a custom UI frontend. Building this end-to-end with the exact cloud services and AI prompt engineering would reasonably take an experienced developer 200-300 hours).*

---

### Tags
*(Maximum 15 keywords, lowercase, comma separated)*

---

### Comment to Reviewer
*Dear Codester Reviewer,*

*Thank you for reviewing SmartHR. Please note:*
*1. The codebase has been fully scrubbed of all personal credentials. We have included a `service-account.example.json` file to serve as a secure template for buyers.*
*2. Default login credentials for testing post-deployment are provided clearly in the documentation (`deploy/README.md`) as `admin@yourcompany.com / admin123`.*
*3. The application features a 1-click GCP deployment script (`deploy-gcp.sh`) which automates the provisioning of Cloud SQL, Cloud Storage, Secret Manager, Cloud Tasks, and Cloud Run.*

*Let me know if you need any additional clarification to approve the listing. Thank you!*
