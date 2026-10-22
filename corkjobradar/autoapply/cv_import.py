"""Read-only PDF review. Nothing here approves facts, stores a CV or attaches annexes."""
from dataclasses import dataclass
import copy
import io

from .documents import validate_document


@dataclass(frozen=True)
class PDFPageReview:
    number: int
    content: bytes
    text: str


@dataclass(frozen=True)
class CVReview:
    primary: PDFPageReview
    annexes: tuple[PDFPageReview, ...]


def review_cv_pdf(content: bytes) -> CVReview:
    """Extract page 1 as CV; rebuild each annex separately, with no annotations/actions.

    The source bytes are never changed. LinkedIn hyperlinks are removed as active
    annotations; their visible text remains available for explicit factual review.
    """
    try:
        from pypdf import PdfReader, PdfWriter
        if len(content) > 10_000_000 or not content.startswith(b'%PDF-'):
            raise ValueError()
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 20:
            raise ValueError()
        root = reader.trailer['/Root']
        if any(key in root for key in ('/OpenAction', '/AA', '/AcroForm')):
            raise ValueError()
        names = root.get('/Names')
        if names and any(key in names.get_object() for key in ('/JavaScript', '/EmbeddedFiles')):
            raise ValueError()
        pages = []
        for number, original in enumerate(reader.pages, 1):
            page = copy.copy(original)
            for key in ('/Annots', '/AA'):
                if key in page:
                    del page[key]
            writer = PdfWriter()
            writer.add_page(page)
            buffer = io.BytesIO()
            writer.write(buffer)
            clean = buffer.getvalue()
            text = (page.extract_text() or '').strip()
            if number == 1:
                text = validate_document(clean, 'pdf')
            pages.append(PDFPageReview(number, clean, text))
        return CVReview(pages[0], tuple(pages[1:]))
    except Exception:
        # Parser errors may include private source content. Do not expose them.
        raise ValueError('CV_PDF_REVIEW_FAILED') from None
