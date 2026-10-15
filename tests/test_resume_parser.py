"""
tests/test_resume_parser.py
────────────────────────────
Unit tests for the PDF text extraction service.
Uses actual in-memory PDFs created with PyMuPDF — no external files needed.
"""

import pytest
import tempfile
from pathlib import Path


def _make_text_pdf(text: str) -> str:
    """Create a temporary PDF with the given text content and return its path."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    doc.save(tmp.name)
    doc.close()
    return tmp.name


def test_extract_valid_pdf():
    from app.services.resume_parser import extract_text_from_pdf
    path = _make_text_pdf("Alice Smith\nPython Developer\nSkills: Python, SQL, Git")
    result = extract_text_from_pdf(path)
    assert result["success"] is True
    assert "Python" in result["text"]
    assert result["page_count"] == 1
    Path(path).unlink(missing_ok=True)


def test_extract_nonexistent_file():
    from app.services.resume_parser import extract_text_from_pdf
    result = extract_text_from_pdf("/tmp/nonexistent_placemate_test.pdf")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_extract_empty_pdf():
    """A PDF with no text should return success=False with a clear message."""
    import fitz
    doc = fitz.open()
    doc.new_page()   # page exists but contains no text
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    doc.save(tmp.name)
    doc.close()

    from app.services.resume_parser import extract_text_from_pdf
    result = extract_text_from_pdf(tmp.name)
    assert result["success"] is False
    assert result["page_count"] == 1
    Path(tmp.name).unlink(missing_ok=True)


def test_extract_multipage_pdf():
    """Multi-page PDFs should concatenate text from all pages."""
    import fitz
    doc = fitz.open()
    # Insert text immediately after new_page — page objects can become stale
    # in some PyMuPDF builds if you hold references across new_page() calls.
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Page one content with Python skills", fontsize=11)
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Page two content with SQL experience", fontsize=11)
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    doc.save(tmp.name)
    doc.close()

    from app.services.resume_parser import extract_text_from_pdf
    result = extract_text_from_pdf(tmp.name)
    assert result["success"] is True
    assert result["page_count"] == 2
    assert "Python" in result["text"]
    assert "SQL" in result["text"]
    Path(tmp.name).unlink(missing_ok=True)
