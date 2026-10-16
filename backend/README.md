# SVPM Admissions API starter

Django REST Framework backend for the React portal. SQLite is the local development default; settings can switch to MySQL using `.env`. Python 3.11+ is required.

## Run locally on Windows

From this `backend` directory:

```powershell
py -m venv .venv
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py makemigrations admissions
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver localhost:8000
```

Open the Django admin at `http://localhost:8000/admin/` and the React portal at `http://localhost:5173/`. Create staff accounts in Django admin; the username is their unique staff ID. Use `/api/health/` to confirm the API responds. Don’t put staff credentials in source files.

## Student onboarding

Before students can register, staff must create their `StudentRecord` in Django admin with the student's PRN, full name, email, mobile number, and department. Student registration checks all four identifying fields against this record. The PRN is also the student's username. Staff accounts are separately created by an administrator.

In local `DEBUG=1`, the email OTP is shown by Django's console email backend and the SMS OTP prints in the Django terminal with `[SVPM DEV SMS]`. Codes expire in five minutes. This local mode is for development only. For actual email delivery, configure SMTP in `.env`. MSG91 SMS delivery is supported with `SMS_OTP_PROVIDER=msg91`, `MSG91_AUTH_KEY`, and `MSG91_SMS_TEMPLATE_ID`; the approved template must place the supplied OTP in `VAR1`. Register the organization, sender/header, and message template as required for Indian SMS delivery. The older generic webhook configuration remains available for a college-managed adapter. Never commit `.env`.

## Local OCR document review

OCR runs locally through Tesseract (LSTM OCR) and does not send student files to a cloud OCR provider. Install Tesseract OCR separately on Windows, install its English language data, then set `TESSERACT_CMD` in `.env` if `tesseract.exe` is not on PATH. The default OCR language is `eng`; set `TESSERACT_LANG` to an installed language code if needed. Install Python dependencies and apply the migration:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
```

After sign-in, the frontend creates an application through `POST /api/applications/` and uploads its mandatory PRN proof plus other documents to `POST /api/documents/` as multipart form data (`application`, `kind`, and `file`). Supported files are JPG, PNG, TIFF, and PDF, up to 3 MB; PDFs are limited to 8 pages. `GET /api/documents/` returns the student's own status. Staff review the queue at `GET /api/staff/documents/`, change a status with `PATCH /api/staff/documents/{id}/`, and download through the staff-only download route.

The service extracts a name match and labeled issue/expiry dates, compares them to the staff-created `StudentRecord`, and stores only those selected fields (not the entire OCR text). Income certificates older than the application's admission start year are marked for re-upload. NCL expiry checks require `DOCUMENT_VALIDITY_CUTOFF_MM_DD=MM-DD` in `.env`; the college must confirm that cycle's cutoff before setting it. At 90% or above, with confident name/OCR results and no date issues, the document is marked `AUTO_CHECK` (automated checks passed); this is distinct from staff `VERIFIED`. If OCR, dates, or a name match are uncertain, the document goes to staff review. An OCR score is not proof of document authenticity or final admission approval. OCR currently runs synchronously during upload, suitable for a local project demo; production traffic should move processing to a background worker and add file malware scanning and retention controls.

## MySQL

Install and start MySQL Server, create an application database and restricted DB user, then edit `.env`: set `DB_ENGINE=mysql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`. Re-run migrations after switching databases. Never commit `.env` or real credentials.

## API routes

- `GET /api/health/` — public health check.
- `GET /api/csrf/` — sets the CSRF cookie for session-authenticated browser requests.
- `GET /api/me/` — current authenticated user.
- `GET/POST /api/applications/` — list or create the signed-in student's continuing-year application.
- `GET/POST /api/documents/` — list the signed-in student's documents or upload one for OCR checks.
- `GET /api/staff/documents/` — staff-only document-review queue.
- `GET/PATCH /api/staff/documents/{id}/` — inspect and update staff review status and note.
- `GET /api/staff/documents/{id}/download/` — staff-only private-file download.
- `POST /api/auth/login/` and `/api/auth/logout/` — session sign-in and sign-out.
- `POST /api/auth/register/start/` and `/api/auth/register/verify/` — PRN-matched registration and email/mobile OTP verification.
- `POST /api/auth/password-reset/start/` and `/api/auth/password-reset/complete/` — OTP-protected password reset.
- `GET /api/staff/students/lookup/?prn=...` — staff-only PRN lookup; masks Aadhaar and writes an audit log.
- `POST /api/fees/estimate/` — authenticated estimate using the supplied fee rules.
- `GET/PATCH /api/staff/shareholder-claims/` — staff-only shareholder claim review route.
- Django admin manages student records, applications, documents, scholarship rows, fee assessments, and shareholder claims.

## Remaining project scope

Student login, registration, dual-channel OTP, password reset, application creation, local OCR document checks, staff document review, and session restoration are connected. Bulk staff record imports, scholarship processing, shareholder claim submission, Razorpay orders and verified webhooks, downloadable receipts, and confirmation messages remain to be built. A payment must never be marked paid based only on a browser response.

Aadhaar is not stored in plaintext; the digest-writing workflow is not implemented, so avoid entering real Aadhaar data in this prototype. Private uploaded files require authenticated download endpoints, file-content scanning, backups/retention controls, HTTPS, and a production security review before live use.
