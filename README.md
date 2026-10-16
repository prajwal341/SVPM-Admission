# SVPM Admissions Portal

A responsive React + TypeScript frontend concept for SVPM College of Engineering admissions. It follows the supplied admission workflow and stack notes: student sign-in and first-time registration with email/mobile OTP steps, separate staff sign-in, 2nd/3rd/4th-year applications, staff-managed document review, scholarship review, fee installments and receipt, and a chatbot entry point. The current screens use demonstration data and local interaction states; they are ready to connect to the planned Django REST Framework API and MySQL-backed services.

## Run locally

1. Install Node.js (LTS).
2. In this folder, run `npm install`.
3. Run `npm run dev` and open the local address Vite prints.

The app opens on the sign-in page. Use **Create an account** to preview the student registration and OTP screens, or **Sign in as staff** to preview the staff review queue. The same supplied high-resolution campus photo is used proportionally on the sign-in and student welcome screens. The floating assistant button opens the chatbot panel. OTP delivery, account storage, password reset, uploads, verification decisions, payment, receipt generation, and the assistant are frontend demonstrations; connect them to secure backend endpoints before production. Staff access must be authorized by the backend and cannot rely on hiding UI controls alone.

## Admission rules supplied so far

- Student admissions are for continuing 2nd-, 3rd-, and 4th-year students.
- First-time student account creation verifies both email and mobile. Returning sign-in does not request OTP; password recovery does.
- Staff receive unique credentials and are responsible for manually uploading and maintaining student records and documents. Only authorized staff should be able to access this function.
- The application should keep students moving through the required steps, show outstanding tasks, and give a clear view of current-year fees and any carried balance.
- Calculate fees using the college's category and gender fee schedule. Where a scholarship amount is applicable and payable to the college, subtract that amount; otherwise show the full applicable fee.
- Use Razorpay for online payment. After successful payment, generate a student-named PDF receipt with the college's approved electronic signature/stamp, provide it for download, and send an admission confirmation.
- When scholarship fees have not been paid to the college, request scholarship application/approval evidence for staff review. Scholarship status should be visible in the student's account.
- The provided offline admission card has been translated into an online form covering course/year and quota, hostel selection, student and parent details, prior admission years, eligibility number, PRN, caste/category, scholarship and bank details, contact/address details, student declaration, and office-only receipt/payment fields.
- PRN entry and upload of PRN proof are mandatory. Staff PRN search uses `GET /api/staff/students/lookup/?prn=<PRN>`; the Django endpoint enforces staff authorization and logs each lookup. Aadhaar is masked in the summary.

The supplied document checklist, scholarship examples, and fee circular are reflected in the frontend preview. The fee circular is headed Academic Year 2026–27 but its newest rate column is 2025–26; the actual 2026–27 schedule, scholarship eligibility rules, approved college signature/stamp, and confirmation message wording still need confirmation. No personal values have been copied from the photographed sample form.

## Plan implemented in the frontend preview (5 Oct 2026)

- Added the admission document checklist from the supplied notes, including mandatory PRN proof and a note that final requirements can vary by category.
- Added a separate scholarship evidence panel with MahaDBT status, approval/application screenshot upload control, and the requested false-information notice.
- Updated the fee estimate to use only the latest (2025–26) column and the user's clarified rules: Open full fee ₹89,350; SC ₹350; eligible girls ₹10,867 except the ₹350 group; ST/NT/TFWS/VJ/DT(A) ₹10,867; OBC/EBC/SBC/EWS ₹50,109 after scholarship deduction; Open with EBC/EWS certificate uses the OBC net rate. Prior unpaid fees are added to the current amount.
- Added the CAP-round MahaDBT guidance and an online shareholder/Sabhasad claim section. The student supplies shareholder details, affidavit, and sugarcane-bill proof; staff manually verifies the claim and settlement in a separate review panel. No automatic shareholder fee deduction or approval is represented.
- Added a staff student directory grouped by FE/SE/TE/BE, with department and text filters, manual add/edit, and CSV import. See the Staff student records section below for the import format.
- Added staff UI for duplicate identifier checks for PRN/email/mobile/Aadhaar, and AI comparison routing at the 90% threshold.
- Added a manual-review queue example and clear prototype notices. The score slider is only a UI demonstration; it does not perform OCR, compare documents, or approve admission.

These are frontend interactions, not a functioning admissions service. The fee document says Academic Year 2026–27, but its latest table column is 2025–26; the values currently follow the user's instruction to use that latest column. Confirm the actual 2026–27 rates with the college before collecting fees. The exact SC/₹350 category and all category eligibility should be confirmed by staff. The Django REST Framework and MySQL backend is still needed for login/OTP, persistent records, secure file storage, server-side duplicate checks, real AI document extraction and comparison, audit logs, protected staff access, and saving/reviewing shareholder claims. Category-specific document requirements also need staff confirmation. Razorpay, PDF receipts, messaging, and real admission decisions remain unconnected.

## Staff student records

The staff dashboard provides FE, SE, TE, and BE tabs. Staff can filter by department, search by PRN/name/email/mobile, add a record, edit a record, or import a CSV list. The API endpoints are staff-only and audit record creation, updates, imports, and PRN lookups. Aadhaar digests and other sensitive fields are not returned by the directory API.

The staff-only Student Documents panel loads a student by PRN, shows one checklist row for every supported document type, accepts uploads up to 3 MB, runs the configured local OCR workflow, and links to the protected document download endpoint. Document types are named explicitly: passport-size photo, Aadhaar, PRN proof, CET result, previous year/semester marksheet or result, FE admission proof/form, first-year eligibility form, 10th and 12th marksheets, 12th leaving certificate, caste certificate, caste validity, non-creamy layer, income certificate, domicile, ration card, scholarship application/approval proof, and other supporting document. Student documents are matched to a staff-verified reference with the same document type; when a serial number can be extracted, OCR compares its one-way digest and sends mismatches or unreadable numbers to manual review. `GET` and multipart `POST /api/staff/student-documents/` are staff-protected. Apply migrations before using the new CET and FE document types.

CSV headers (UTF-8): `prn,full_name,email,mobile,department,year_level,first_year_admission`. `year_level` must be `FE`, `SE`, `TE`, or `BE`; `first_year_admission` is optional, e.g. `2023-24`. A PRN already in the database updates that student; duplicate PRN/email/mobile conflicts are reported by row. Imports are limited to 5,000 rows and 3 MB per CSV. The standard department names match the online admission branch list.

After adding the year-level field, run the migration from the backend folder:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

## Structure

- `src/App.tsx` — student dashboard, staff workspace, section views, and assistant panel
- `src/styles.css` — responsive portal styles and Tailwind CSS v4 import
- `public/images/` — supplied SVPM logo and campus photos used on the login and welcome screens
- `vite.config.ts` — Vite, React, and Tailwind plugins
- `backend/` — Django REST Framework API starter; see [backend/README.md](backend/README.md) for Windows setup
