"""
app/services/resume_parser.py
─────────────────────────────
PDF text extraction using PyMuPDF (fitz).

This module is purely deterministic — no AI, no network.
It extracts text from a PDF file and returns a structured result.

Why PyMuPDF?
  - Fast and reliable for text-based PDFs.
  - Works offline with no API calls.
  - Exposes page count and can detect empty/scanned PDFs.

Limitations (documented, not hidden):
  - Scanned PDFs (image-only) will return empty text. The caller receives
    a clear error and should offer a manual-entry fallback.
  - Password-protected PDFs are not supported in the MVP.
  - Complex multi-column layouts may produce garbled text order.
"""

from pathlib import Path
from typing import TypedDict


class ExtractionResult(TypedDict):
    success: bool
    text: str
    page_count: int
    message: str
    error: str


def extract_text_from_pdf(file_path: str) -> ExtractionResult:
    """
    Extract all text from a PDF file at file_path.

    Returns a dict with:
      success     — True if usable text was found
      text        — the extracted text (empty string on failure)
      page_count  — number of pages in the document
      message     — human-readable status
      error       — error description if success is False

    This function never raises. All exceptions are caught and returned
    in the error field so the caller can show a meaningful message.
    """
    result: ExtractionResult = {
        "success": False,
        "text": "",
        "page_count": 0,
        "message": "",
        "error": "",
    }

    path = Path(file_path)
    if not path.exists():
        result["error"] = f"File not found: {file_path}"
        result["message"] = "The uploaded file could not be located on disk."
        return result

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        result["page_count"] = doc.page_count

        if doc.page_count == 0:
            result["error"] = "PDF has no pages."
            result["message"] = "The uploaded file appears to be an empty PDF."
            doc.close()
            return result

        # Extract text from all pages
        pages_text: list[str] = []
        for page in doc:
            pages_text.append(page.get_text())  # type: ignore[attr-defined]

        doc.close()

        full_text = "\n\n".join(pages_text).strip()

        # Detect scanned/image-only PDFs
        if not full_text or len(full_text) < 50:
            result["error"] = (
                "No extractable text found. This may be a scanned (image-only) PDF."
            )
            result["message"] = (
                "We could not extract text from this PDF. "
                "If this is a scanned resume, please use the manual profile entry instead, "
                "or re-export your resume as a text-based PDF."
            )
            return result

        result["success"] = True
        result["text"] = full_text
        result["message"] = (
            f"Successfully extracted text from {doc.page_count} page(s)."
            if doc.page_count > 1
            else "Successfully extracted text from 1 page."
        )
        # Correct the page count message (doc was already closed above)
        result["message"] = (
            f"Successfully extracted text from {result['page_count']} page(s)."
        )
        return result

    except Exception as exc:
        result["error"] = str(exc)
        result["message"] = (
            "An error occurred while reading the PDF. "
            "Please try again or use manual profile entry."
        )
        return result
