"""Synthetic PDFs only; never load a user's personal CV in regression tests."""
import hashlib
import io
import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from corkjobradar.autoapply.cv_import import review_cv_pdf
from corkjobradar.autoapply.documents import store_document, document_bytes, render_cv, render_letter
from corkjobradar.autoapply.vault import approve_fact, candidate_snapshot
from test_autoapply_vault import populate


def pdf_bundle():
    buffer = io.BytesIO()
    canvas = Canvas(buffer)
    canvas.drawString(40, 740, 'SYNTHETIC CV ONLY: Technical support in training.')
    canvas.drawString(40, 720, 'https://www.linkedin.com/in/synthetic-only/')
    canvas.linkURL('https://www.linkedin.com/in/synthetic-only/', (40, 710, 400, 735))
    canvas.showPage()
    canvas.drawString(40, 740, 'SYNTHETIC REFERENCE LETTER - NOT PART OF CV')
    canvas.showPage()
    canvas.drawString(40, 740, 'SYNTHETIC CERTIFICATE - NOT PART OF CV')
    canvas.save()
    return buffer.getvalue()


def test_pdf_review_is_read_only_and_keeps_annexes_separate(db):
    source = pdf_bundle(); original_hash = hashlib.sha256(source).hexdigest()
    review = review_cv_pdf(source)
    assert len(PdfReader(io.BytesIO(review.primary.content)).pages) == 1
    assert 'Technical support in training' in review.primary.text
    assert 'linkedin.com/in/synthetic-only/' in review.primary.text
    assert 'REFERENCE' not in review.primary.text and 'CERTIFICATE' not in review.primary.text
    assert [annex.number for annex in review.annexes] == [2, 3]
    assert 'REFERENCE LETTER' in review.annexes[0].text
    assert 'CERTIFICATE' in review.annexes[1].text
    for page in (review.primary, *review.annexes):
        reader = PdfReader(io.BytesIO(page.content))
        assert len(reader.pages) == 1 and '/Annots' not in reader.pages[0]
    assert hashlib.sha256(source).hexdigest() == original_hash
    assert not db.rows('SELECT * FROM candidate_facts')
    assert not db.rows('SELECT * FROM candidate_documents')


def test_backend_rejects_multpage_cv_even_after_explicit_review(db):
    source = pdf_bundle()
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(source)).pages:
        if '/Annots' in page: del page['/Annots']
        writer.add_page(page)
    buffer = io.BytesIO(); writer.write(buffer)
    with pytest.raises(ValueError, match='FIRST_PAGE_ONLY'):
        store_document(db, buffer.getvalue(), 'pdf', True)
    assert not db.rows('SELECT * FROM candidate_documents')


def test_first_page_requires_separate_explicit_claim_and_document_approvals(db):
    review = review_cv_pdf(pdf_bundle())
    with pytest.raises(ValueError, match='APPROVED_CLAIMS'):
        store_document(db, review.primary.content, 'pdf', True)
    approve_fact(db, 'claim:training', {'section':'Skills', 'text_en':'Technical support in training.'}, 'SYNTHETIC CV page 1', True)
    with pytest.raises(ValueError, match='EXPLICIT_DOCUMENT_REVIEW'):
        store_document(db, review.primary.content, 'pdf', False)
    doc = store_document(db, review.primary.content, 'pdf', True)
    content, extension, _ = document_bytes(db, doc)
    assert content == review.primary.content and extension == 'pdf'
    assert len(db.rows('SELECT * FROM candidate_documents')) == 1
    assert not db.rows('SELECT * FROM application_attempts')


@pytest.mark.parametrize('source',[b'not a PDF', b'%PDF- malformed', b'%PDF-' + b'0'*10_000_000],ids=['wrong-header','malformed','oversize'])
def test_invalid_pdf_is_private_and_rejected(source):
    with pytest.raises(ValueError, match='^CV_PDF_REVIEW_FAILED$'):
        review_cv_pdf(source)


def test_pdf_with_javascript_is_rejected():
    writer = PdfWriter(); writer.add_blank_page(width=600, height=800)
    writer.add_js("app.alert('SYNTHETIC ONLY');")
    buffer = io.BytesIO(); writer.write(buffer)
    with pytest.raises(ValueError, match='^CV_PDF_REVIEW_FAILED$'):
        review_cv_pdf(buffer.getvalue())


def test_linkedin_requires_user_approval_and_exact_profile_url(db):
    url = 'https://www.linkedin.com/in/synthetic-only/'
    with pytest.raises(ValueError, match='EXPLICIT_FACT_APPROVAL'):
        approve_fact(db, 'linkedin_url', url, 'synthetic', False)
    for invalid in ('https://linkedin.com.evil.invalid/in/test', 'javascript:evil', 'https://linkedin.com/company/test'):
        with pytest.raises(ValueError, match='INVALID_LINKEDIN'):
            approve_fact(db, 'linkedin_url', invalid, 'synthetic', True)
    approve_fact(db, 'linkedin_url', url, 'SYNTHETIC CV page 1', True)
    assert candidate_snapshot(db)['linkedin_url'] == url


def test_document_preparation_rechecks_it_scope(db):
    populate(db)
    general = {'title':'Warehouse Operative', 'company':'SYNTHETIC SOFTWARE ONLY',
               'category':'IT', 'detail_complete':True, 'description':'Pick and pack goods.'}
    for renderer in (render_cv, render_letter):
        with pytest.raises(PermissionError, match='NON_IT_EXCLUDED'):
            if renderer is render_cv: renderer(candidate_snapshot(db), job=general)
            else: renderer(candidate_snapshot(db), general)
