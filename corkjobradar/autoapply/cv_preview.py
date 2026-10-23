"""Render the validated one-page PDF in memory. No files, remote services or logs."""
import io
from .documents import validate_document


def render_pdf_page(content, page_number=0):
    """In-memory raster only. Callers validate their own CV/reference contract."""
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(content) as document:
        if type(page_number) is not int or not 0 <= page_number < len(document):
            raise ValueError('INVALID_PREVIEW_PAGE')
        page = document[page_number]
        try:
            bitmap = page.render(scale=1.25)
            try:
                picture = bitmap.to_pil()
                try:
                    output = io.BytesIO()
                    picture.save(output, format='PNG')
                    return output.getvalue()
                finally:
                    picture.close()
            finally:
                bitmap.close()
        finally:
            page.close()


def pdf_preview(content, *, page_number=0, max_pages=1):
    try:
        validate_document(content, 'pdf')
        from pypdf import PdfReader
        if max_pages not in (1, 2) or not 1 <= len(PdfReader(io.BytesIO(content)).pages) <= max_pages:
            raise ValueError('CV_PAGE_POLICY_EXCEEDED')
        return render_pdf_page(content, page_number)
    except Exception:
        raise ValueError('CV_PREVIEW_UNAVAILABLE') from None


def show_pdf_preview(content, extension):
    if extension != 'pdf':
        return
    import streamlit as st
    try:
        st.image(pdf_preview(content), caption='Vista previa del PDF exacto que estás revisando', output_format='PNG')
    except ValueError:
        st.info('Vista previa no disponible. Descarga y revisa el documento completo antes de aprobarlo.')
