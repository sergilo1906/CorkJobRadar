"""Private Windows render evidence. Generates drafts ONLY, never approves or sends.

Explicitly selected stored jobs may have unmet eligibility requirements: this is
a document quality exercise, not certification that all three jobs are suitable.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from corkjobradar.config import ROOT, now
from corkjobradar.db import Database
from corkjobradar.autoapply.vault import candidate_snapshot, private_folder
from corkjobradar.autoapply.job_documents import create_job_version, load_job_version, review_file
from corkjobradar.autoapply.documents import validate_document
from corkjobradar.autoapply.reference_library import import_reference, reference_bytes
from corkjobradar.autoapply.broad_selection import assess_selection


def render_office(source, destination, workspace):
    office=Path('C:/Program Files/LibreOffice/program/soffice.com')
    if not office.is_file(): raise RuntimeError('LIBREOFFICE_UNAVAILABLE')
    environment=os.environ.copy();environment.update(TEMP=str(workspace),TMP=str(workspace))
    profile='-env:UserInstallation='+(workspace/'office-profile').as_uri()
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=subprocess.SW_HIDE
    if not (workspace/'office-initialized').exists():
        initialized=subprocess.run([str(office),profile,'--headless','--terminate_after_init'],env=environment,capture_output=True,timeout=55,startupinfo=startup)
        if initialized.returncode: raise RuntimeError('OFFICE_PROFILE_INIT_FAILED')
        (workspace/'office-initialized').write_text('initialized',encoding='ascii')
    result=subprocess.run([str(office),profile,'--headless','--norestore','--nofirststartwizard',
        '--convert-to','pdf','--outdir',str(destination),str(source)],env=environment,capture_output=True,timeout=55,startupinfo=startup)
    if result.returncode: raise RuntimeError('OFFICE_RENDER_FAILED')
    target=destination/(source.stem+'.pdf');deadline=time.monotonic()+40
    while not target.exists() and time.monotonic()<deadline: time.sleep(.1)
    if not target.is_file(): raise RuntimeError('OFFICE_PDF_NOT_CREATED')
    return target


def screenshots(raw, prefix):
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(raw) as doc:
        for n in range(len(doc)):
            page=doc[n]
            try:
                for scale,label in ((1,'100'),(1.5,'150')):
                    bitmap=page.render(scale=scale);im=bitmap.to_pil()
                    try:im.save(str(prefix)+f'-p{n+1}-{label}.png')
                    finally:im.close();bitmap.close()
            finally:page.close()


def extracted_text(raw):
    from pypdf import PdfReader
    text='\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(raw)).pages)
    # Word legitimately wraps a compound at its existing hyphen (first- / line).
    # Join only printed line breaks there; do not remove hyphens or words.
    text=re.sub(r'(?<=\w)-[ \t]*\r?\n[ \t]*(?=\w)', '-', text)
    return ' '.join(text.split())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path)
    p.add_argument('--support-job',required=True);p.add_argument('--developer-job',required=True);p.add_argument('--qa-job',required=True)
    p.add_argument('--hold-cv-id',type=int);p.add_argument('--label',required=True)
    args=p.parse_args()
    if not re.fullmatch(r'per-job-[a-z0-9-]+',args.label):raise ValueError('SAFE_EVIDENCE_LABEL_REQUIRED')
    report_path=ROOT/'logs'/(args.label+'.json')
    if report_path.exists():raise ValueError('PRESERVE_PREVIOUS_EVIDENCE')
    raw=args.source.read_bytes();original_sha=hashlib.sha256(raw).hexdigest()
    db=Database();candidate=candidate_snapshot(db)
    before={t:db.rows('SELECT * FROM '+t+' ORDER BY id') for t in ('candidate_facts','candidate_documents','application_attempts','autoapply_control')}
    workspace=private_folder(db)/('per-job-render-'+uuid4().hex[:10]);workspace.mkdir()
    if args.hold_cv_id:
        existing=db.rows('SELECT approved_at FROM candidate_documents WHERE id=?',(args.hold_cv_id,))
        if not existing or existing[0]['approved_at']:raise ValueError('QUALITY_HOLD_REQUIRES_EXPLICIT_PENDING_CV')
        if not db.rows("SELECT id FROM job_document_events WHERE kind='GENERAL_CV_QUALITY_HOLD' AND json_extract(details,'$.document_id')=?",(args.hold_cv_id,)):
            db.execute("INSERT INTO job_document_events(kind,created_at,details) VALUES('GENERAL_CV_QUALITY_HOLD',?,?)",(now(),json.dumps({'document_id':args.hold_cv_id,'reason':'USER_REJECTED_LAYOUT_PENDING_REPLACEMENT'})))
    references=[]
    for page,issuer,kind,issued,notes in (
        (2,'SIE','IT_RECOMMENDATION','2026-09-23','Employment dates match the approved IT period. Letter describes joining as an intern and additional technical tasks. Contract/role wording and unapproved tasks require personal review; they have not been added to facts.'),
        (3,'GAS_REUSENSE','EMPLOYMENT_RECOMMENDATION','2026-01-09','Scanned recommendation. Date is the letter date, not employment dates. Role and duties are source evidence pending professional-profile review.'),
        (4,'CARRIAGE_FOOD_SERVICES','EMPLOYMENT_CONFIRMATION','2026-09-21','Scanned employment confirmation, not a qualitative recommendation. Employment dates and role label require review against the CV; no new professional fact has been approved.')):
        rid=import_reference(db,raw,issuer=issuer,document_type=kind,source_page=page,issued_on=issued,notes=notes,consent_to_store=True)
        stored,row=reference_bytes(db,rid);assert stored==raw
        references.append({'id':rid,'source_page':page,'classification':kind,'reviewed':bool(row['reviewed_at']),
                           'sharing_authorized':row['metadata']['share_authorized'],'original_byte_identical':True,
                           'standalone_original_required_for_attachment':True})
    variants=[]
    for family,jid in (('IT_SUPPORT',args.support_job),('JUNIOR_DEVELOPER',args.developer_job),('QA_TESTER',args.qa_job)):
        vid=create_job_version(db,jid,family=family);_,payload=load_job_version(db,vid)
        stem=workspace/family.lower();office_dir=workspace/(family.lower()+'-office');office_dir.mkdir()
        for ext in ('pdf','docx'):
            (stem.with_suffix('.'+ext)).write_bytes(review_file(db,vid,extension=ext))
            (workspace/(family.lower()+'-letter.'+ext)).write_bytes(review_file(db,vid,'COVER_LETTER',ext))
        rendered=render_office(stem.with_suffix('.docx'),office_dir,workspace)
        pdf_raw=stem.with_suffix('.pdf').read_bytes();word_raw=rendered.read_bytes()
        from pypdf import PdfReader
        selected=set(payload['plan']['selected_fact_ids']);claims=[c for c in candidate['_claims'] if c['id'] in selected]
        for content in (pdf_raw,word_raw):
            assert len(PdfReader(io.BytesIO(content)).pages)<=payload['max_pages']
            # Office may add clickable URL annotations to its viewing PDF.
            # Read that derivative as text, never import/export it as the
            # strict application CV. The generated CV remains strictly validated.
            text=extracted_text(content)
            assert all(' '.join(c['text_en'].split()) in text for c in claims)
            assert all(candidate[k] in text for k in ('full_name','email','linkedin_url') if candidate.get(k))
            assert 'Institut Baix Camp' in text and '2022-2024' in text
        validate_document(pdf_raw,'pdf')
        screenshots(pdf_raw,stem);screenshots(word_raw,office_dir/'word')
        letter_docx=workspace/(family.lower()+'-letter.docx')
        letter_word=render_office(letter_docx,office_dir,workspace).read_bytes()
        letter_pdf=review_file(db,vid,'COVER_LETTER','pdf')
        for content in (letter_pdf,letter_word):
            text=extracted_text(content)
            assert payload['title'] in text and payload['company'] in text
            assert set(payload['letter']['fact_ids']).issubset({c['id'] for c in candidate['_claims']})
            assert all(' '.join(line.split()) in text for line in payload['letter']['lines'])
        screenshots(letter_pdf,workspace/(family.lower()+'-letter'))
        screenshots(letter_word,office_dir/'letter-word')
        job=db.rows('SELECT * FROM jobs WHERE id=?',(jid,))[0];selection=assess_selection(db,job,candidate)
        variants.append({'family':family,'version_id':vid,'job_id':jid,'selected_fact_ids':sorted(selected),
                         'omitted_fact_ids':payload['plan']['omitted_fact_ids'],'pdf_pages':len(PdfReader(io.BytesIO(pdf_raw)).pages),
                         'office_pages':len(PdfReader(io.BytesIO(word_raw)).pages),'word_renderer':'LibreOffice; Microsoft Word not tested',
                         'all_selected_facts_and_contacts_verified':True,'approved':False,'private_preview_prefix':str(stem.relative_to(ROOT)),
                         'cover_letter_word_count':payload['letter']['word_count'],'cover_letter_evidence_links':len(payload['letter']['links']),
                         'cover_letter_pdf_and_docx_text_verified':True,
                         'selection_exclusions':selection['exclusions'],'selection_pending':selection['essential_pending']})
    assert len({tuple(v['selected_fact_ids']) for v in variants})==3
    for table,rows in before.items():assert db.rows('SELECT * FROM '+table+' ORDER BY id')==rows
    assert hashlib.sha256(args.source.read_bytes()).hexdigest()==original_sha
    report={'created_at':now(),'status':'RENDERED_REQUIRES_VISUAL_REVIEW','variants':variants,'references':references,
            'original_unchanged':True,'approved_fact_count':len(candidate['_claims'])+len(candidate['_fact_ids']),
            'critical_tables_unchanged':True,'live_enabled':False,'external_requests':0,'applications_sent':0,
            'private_workspace':str(workspace.relative_to(ROOT))}
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'report':str(report_path.relative_to(ROOT)),
                      'private_workspace':report['private_workspace'],'versions':[v['version_id'] for v in variants]}))


if __name__=='__main__':main()
