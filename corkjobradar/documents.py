"""Text extraction with explicit bounds; never silently truncate a document."""
import io
import zipfile
from docx import Document
from pypdf import PdfReader


def document_text(content, filename):
    if len(content) > 15 * 1024 * 1024:
        raise ValueError('Documento mayor de 15 MiB; requiere revisión manual')
    stream = io.BytesIO(content)
    if content.startswith(b'%PDF-'):
        reader = PdfReader(stream)
        if reader.is_encrypted or len(reader.pages) > 150:
            raise ValueError('PDF cifrado o con más de 150 páginas; revisión manual')
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    elif filename.lower().split('?')[0].endswith('.docx') and zipfile.is_zipfile(stream):
        with zipfile.ZipFile(stream) as archive:
            if sum(x.file_size for x in archive.infolist()) > 50 * 1024 * 1024:
                raise ValueError('DOCX descomprimido excede 50 MiB; revisión manual')
        stream.seek(0)
        doc = Document(stream)
        # iter_inner_content keeps paragraph/table order, including requirements in tables.
        text = '\n'.join(item.text if hasattr(item, 'text') else '\n'.join(
            ' | '.join(cell.text for cell in row.cells) for row in item.rows)
            for item in doc.iter_inner_content())
    else:
        raise ValueError('Formato no extraíble: solo PDF con texto y DOCX; DOC antiguo/imagen requiere revisión')
    if len(text.split()) < 30:
        raise ValueError('Documento sin texto sustancial extraíble; posible imagen o escaneo')
    return text.strip()
