"""Render the validated one-page PDF in memory. No files, remote services or logs."""
import io
from .documents import validate_document


def pdf_preview(content):
    try:
        validate_document(content, 'pdf')
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(content) as document:
            if len(document) != 1:
                raise ValueError('ONE_PAGE_CV_REQUIRED')
            page = document[0]
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
