"""Local OCR and conservative admission-document checks.

OCR confidence measures text recognition quality, not document authenticity.
The service stores only selected fields, not the complete OCR text.
"""
from __future__ import annotations

import io
import hashlib
import hmac
import re
from datetime import date

from django.conf import settings


class OCRUnavailable(RuntimeError):
    pass


def _read_pages(file_obj):
    """Yield PIL images for supported image and PDF uploads."""
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise OCRUnavailable("Install Pillow in the backend virtual environment to enable OCR.") from exc

    file_obj.open("rb")
    raw = file_obj.read()
    file_obj.close()
    if raw.startswith(b"%PDF-"):
        try:
            import fitz
        except ImportError as exc:
            raise OCRUnavailable("PDF OCR needs PyMuPDF. Install the backend requirements and retry.") from exc
        try:
            document = fitz.open(stream=raw, filetype="pdf")
        except Exception as exc:
            raise ValueError("The uploaded PDF could not be opened.") from exc
        if document.page_count > 8:
            raise ValueError("PDFs can contain at most 8 pages for automated review.")
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            yield ImageOps.exif_transpose(image).convert("RGB")
        return

    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        image = Image.open(io.BytesIO(raw))
    except Exception as exc:
        raise ValueError("Upload a readable JPG, PNG, TIFF, or PDF document.") from exc
    if getattr(image, "n_frames", 1) > 1:
        image.seek(0)
    yield ImageOps.exif_transpose(image).convert("RGB")


def _extract_ocr(file_obj):
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError as exc:
        raise OCRUnavailable("Install pytesseract in the backend virtual environment to enable OCR.") from exc

    try:
        # On Windows, set TESSERACT_CMD to the installed tesseract.exe path.
        command = getattr(settings, "TESSERACT_CMD", "")
        if command:
            pytesseract.pytesseract.tesseract_cmd = command
        page_text, confidences = [], []
        for image in _read_pages(file_obj):
            data = pytesseract.image_to_data(image, output_type=Output.DICT,
                                             lang=getattr(settings, "TESSERACT_LANG", "eng"), config="--psm 3")
            words = [word.strip() for word in data["text"] if word and word.strip()]
            page_text.append(" ".join(words))
            confidences.extend(float(value) for value, word in zip(data["conf"], data["text"])
                               if word and word.strip() and float(value) >= 0)
        if not page_text or not any(page_text):
            return "", 0.0
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return "\n".join(page_text), round(confidence, 2)
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise OCRUnavailable("Tesseract OCR is not installed or TESSERACT_CMD is incorrect.") from exc
    except pytesseract.TesseractError as exc:
        raise OCRUnavailable("Tesseract could not load the configured OCR language data. Install the language pack or update TESSERACT_LANG.") from exc


DATE_PATTERN = re.compile(r"(?<!\d)(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})(?!\d)")


def _parse_date(value):
    parts = re.split(r"[./-]", value)
    try:
        if len(parts[0]) == 4:
            year, month, day = map(int, parts)
        else:
            day, month, year = map(int, parts)
            if year < 100:
                year += 2000 if year < 70 else 1900
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def _dates_near_labels(text, labels):
    found = []
    for line in text.splitlines():
        if any(label in line.casefold() for label in labels):
            for match in DATE_PATTERN.finditer(line):
                parsed = _parse_date(match.group(1))
                if parsed:
                    found.append(parsed)
    return found


def _normal_words(value):
    return re.findall(r"[a-z0-9]+", value.casefold())


def _identity_matches(text, student):
    text_words = set(_normal_words(text))
    name_words = [word for word in _normal_words(student.full_name) if len(word) > 1]
    name_score = sum(word in text_words for word in name_words) / len(name_words) if name_words else 0

    normalized_prn = "".join(_normal_words(student.prn))
    normalized_text = "".join(_normal_words(text))
    prn_found = bool(normalized_prn and normalized_prn in normalized_text)
    return round(name_score * 100, 2), prn_found


def _document_reference_digest(text, kind):
    """Extract a labeled serial/seat number without persisting the raw value."""
    if kind in {"CASTE", "CASTE_VALIDITY", "NCL", "INCOME_CERTIFICATE", "DOMICILE"}:
        label = r"(?:certificate|cert)\s*(?:no\.?|number|id|#)"
    elif kind in {"CET_RESULT"}:
        label = r"(?:candidate|application|seat|roll)\s*(?:no\.?|number|id|#)"
    elif kind in {"MARKSHEET", "SSC_MARKSHEET", "HSC_MARKSHEET", "ELIGIBILITY", "FE_ADMISSION_PROOF"}:
        label = r"(?:seat|roll|enrol?ment|registration|certificate)\s*(?:no\.?|number|id|#)"
    else:
        return None
    match = re.search(rf"\b{label}\s*[:#.-]?\s*([A-Z0-9][A-Z0-9/-]{{3,29}})", text, re.IGNORECASE)
    if not match:
        return None
    normalized = re.sub(r"[^A-Z0-9]", "", match.group(1).upper())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else None


def verify_document(document):
    """OCR a saved document, compare identity and dates, then persist a review run."""
    from django.utils import timezone
    from .models import VerificationRun

    try:
        text, ocr_confidence = _extract_ocr(document.file)
    except OCRUnavailable as exc:
        document.ocr_status = "UNAVAILABLE"
        document.validation_reasons = [str(exc), "Document remains pending staff review."]
        document.ocr_processed_at = timezone.now()
        document.save(update_fields=["ocr_status", "validation_reasons", "ocr_processed_at"])
        return None
    except (ValueError, OSError) as exc:
        document.ocr_status = "FAILED"
        document.review_status = document.ReviewStatus.NEEDS_REUPLOAD
        document.validation_reasons = [str(exc)]
        document.ocr_processed_at = timezone.now()
        document.save(update_fields=["ocr_status", "review_status", "validation_reasons", "ocr_processed_at"])
        return None

    student = document.student
    name_score, prn_found = _identity_matches(text, student)
    extracted = {"name_match_percent": name_score, "prn_found": prn_found}
    reasons = []
    requires_new_upload = False
    score = min(100.0, name_score * 0.75 + ocr_confidence * 0.25)

    kind = document.kind
    reference_digest = _document_reference_digest(text, kind)
    if reference_digest:
        extracted["document_reference_digest"] = reference_digest
    if document.application_id:
        from .models import StudentDocument
        reference_document = (StudentDocument.objects.filter(student_id=student.pk, kind=kind,
                                                               application__isnull=True,
                                                               review_status=StudentDocument.ReviewStatus.VERIFIED)
                              .exclude(pk=document.pk).order_by("-uploaded_at").first())
        extracted["reference_document_type"] = kind
        if not reference_document:
            reasons.append(f"No staff-verified {kind.replace('_', ' ').lower()} reference file was found; manual comparison is required.")
        else:
            extracted["reference_document_id"] = reference_document.pk
            reference_digest = reference_document.extracted_fields.get("document_reference_digest")
            if reference_digest and extracted.get("document_reference_digest"):
                matched = hmac.compare_digest(reference_digest, extracted["document_reference_digest"])
                extracted["reference_match"] = matched
                if not matched:
                    reasons.append(f"Document reference does not match the staff-verified {kind.replace('_', ' ').lower()} file.")
                    requires_new_upload = True
            else:
                extracted["reference_match"] = None
                reasons.append(f"A staff-verified {kind.replace('_', ' ').lower()} file exists, but OCR could not read a comparable serial number; manual side-by-side comparison is required.")

    if name_score < 75:
        reasons.append("The document name did not match the staff student record confidently.")
    if prn_found:
        extracted["prn_match"] = True
    # A PRN printed on the document is a strong identifier; otherwise name matching is used.
    normalized_prn = "".join(_normal_words(student.prn))
    if normalized_prn and any("".join(_normal_words(token)) == normalized_prn for token in re.findall(r"[A-Za-z0-9-]+", text)):
        extracted["prn_match"] = True
    elif prn_found:
        extracted["prn_match"] = True
    else:
        extracted["prn_match"] = False

    issue_dates = _dates_near_labels(text, ("date of issue", "issued on", "issue date", "date issued"))
    expiry_dates = _dates_near_labels(text, ("valid upto", "valid up to", "valid till", "valid until", "validity up to", "expiry", "expires on", "date of expiry"))
    issue_date = issue_dates[-1] if issue_dates else None
    expiry_date = expiry_dates[-1] if expiry_dates else None
    if issue_date:
        extracted["issue_date"] = issue_date.isoformat()
        if issue_date > timezone.localdate():
            reasons.append("The detected issue date is in the future; staff must review the document.")
    if expiry_date:
        extracted["expiry_date"] = expiry_date.isoformat()

    application = document.application
    start_year = None
    end_year = None
    if application:
        match = re.match(r"^(\d{4})\s*[-/]\s*(\d{2,4})$", application.academic_year)
        if match:
            start_year = int(match.group(1))
            suffix = match.group(2)
            end_year = int(suffix) if len(suffix) == 4 else (start_year // 100) * 100 + int(suffix)
            if end_year < start_year:
                end_year += 100

    if kind == document.Kind.INCOME_CERTIFICATE:
        if issue_date is None:
            reasons.append("Could not read the income certificate issue date; staff must review it.")
        elif start_year and issue_date.year < start_year:
            reasons.append(f"Income certificate is from {issue_date.year}; a certificate issued for admission year {start_year}-{str(end_year)[-2:]} is required.")
            requires_new_upload = True
    cutoff_mm_dd = getattr(settings, "DOCUMENT_VALIDITY_CUTOFF_MM_DD", "")
    if kind == document.Kind.NCL and expiry_date is None:
        reasons.append("Could not read the NCL expiry date; staff must review it.")
    if expiry_date:
        if not end_year or not cutoff_mm_dd:
            reasons.append("Expiry date was read, but the college admission-cycle validity cutoff is not configured.")
        else:
            try:
                month, day = map(int, cutoff_mm_dd.split("-"))
                cutoff = date(end_year, month, day)
                if expiry_date < cutoff:
                    reasons.append(f"Document expires before the configured admission validity date ({cutoff.isoformat()}).")
                    requires_new_upload = True
            except ValueError:
                reasons.append("The configured document-validity cutoff is invalid; staff must review it.")

    decision = VerificationRun.Decision.AUTO_CHECK if score >= 90 and name_score >= 90 and ocr_confidence >= 80 and not reasons else VerificationRun.Decision.MANUAL_REVIEW
    document.ocr_status = "COMPLETED"
    document.ocr_confidence = ocr_confidence
    document.extracted_fields = extracted
    document.validation_score = round(score, 2)
    document.validation_reasons = reasons
    document.issue_date = issue_date
    document.expiry_date = expiry_date
    document.ocr_processed_at = timezone.now()
    document.review_status = (document.ReviewStatus.NEEDS_REUPLOAD if requires_new_upload else
                              document.ReviewStatus.AUTO_CHECK if decision == VerificationRun.Decision.AUTO_CHECK else
                              document.ReviewStatus.MANUAL)
    document.save(update_fields=["ocr_status", "ocr_confidence", "extracted_fields", "validation_score",
                                 "validation_reasons", "issue_date", "expiry_date", "ocr_processed_at", "review_status"])

    if "prn_match" in extracted and not extracted["prn_match"]:
        reasons.append("PRN was not found on this document; the staff record name was used for matching.")
        document.validation_reasons = reasons
        document.save(update_fields=["validation_reasons"])
    return VerificationRun.objects.create(
        application=application,
        document=document,
        score=round(score, 2),
        decision=decision,
        reasons=reasons,
        provider="tesseract-local",
        model_version="configured-local-engine",
    ) if application else None
