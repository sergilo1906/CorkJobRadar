"""Single CV presentation model; never creates facts, consent or database writes."""
import io
import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape


SECTIONS = (
    ('Profile', 'Professional Profile'),
    ('Skills', 'Core Capabilities'),
    ('Experience', 'Experience'),
    ('Projects', 'Selected Projects'),
    ('Education', 'Education & Training'),
    ('Additional Experience', 'Additional Experience'),
    ('Languages', 'Languages'),
    ('Availability', 'Availability'),
)


@dataclass(frozen=True)
class ReferenceStyle:
    """A4 reference geometry shared by PDF and Word; points, not screen pixels."""
    margin: float = 42
    top: float = 32
    bottom: float = 36
    navy: str = '193F68'
    muted: str = '647184'
    rule: str = 'CBD8E5'
    panel: str = 'F2F5F8'
    name_size: float = 23
    heading_size: float = 10
    body_size: float = 9.5
    contact_size: float = 8.5


REFERENCE = ReferenceStyle()
LAYOUT_VERSION = 'REFERENCE_A4_V2'


def cv_sections(candidate, job=None):
    """Keep every approved claim verbatim; job text can affect ordering only."""
    groups = {key: [] for key, _ in SECTIONS}
    vocabulary = set(re.findall(r'[a-z]{3,}', (
        (job or {}).get('title', '') + ' ' + (job or {}).get('description', '')).lower()))
    for claim in candidate['_claims']:
        section = claim['section']
        if section not in groups:
            raise ValueError('UNSUPPORTED_CV_SECTION')
        text = claim['text_en']
        # Older approved profiles stored project descriptions among skills.
        # Move complete claims only; do not paraphrase or infer missing experience.
        if section == 'Skills' and re.search(
                r'\b(?:project|booking platform|data automation)\b', text, re.I):
            section = 'Projects'
        groups[section].append(text)
    result = []
    for key, label in SECTIONS:
        claims = groups[key]
        if key == 'Education':
            # Qualifications before supplementary courses; exact statements stay
            # intact, including studies still in progress in other profiles.
            claims = sorted(claims, key=lambda text: not bool(re.search(
                r'\b(?:qualification|CFGS|degree|diploma)\b', text, re.I)))
        # Preserve employment chronology and title/bullet association. Only skills
        # and standalone projects may be ranked by literal vacancy vocabulary.
        if vocabulary and key in {'Skills', 'Projects'}:
            claims = sorted(claims, key=lambda text: -len(vocabulary.intersection(
                re.findall(r'[a-z]{3,}', text.lower()))))
        if claims:
            result.append((label, claims))
    return result


def _font_files():
    pairs = (
        ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    )
    for regular, bold in pairs:
        if Path(regular).is_file() and Path(bold).is_file():
            return regular, bold
    raise RuntimeError('UNICODE_FONT_UNAVAILABLE')


def render_professional_cv(candidate, extension, job=None):
    sections = cv_sections(candidate, job)
    contact = ' | '.join(candidate[k] for k in ('email', 'phone', 'location') if candidate.get(k))
    linkedin = candidate.get('linkedin_url')
    # Measure once for BOTH formats. A DOCX must not silently overflow while its
    # PDF counterpart fails. Never truncate or shrink below a readable 9 pt.
    size = _fit_size(candidate['full_name'], contact, linkedin, sections)
    if extension == 'pdf':
        return _pdf(candidate['full_name'], contact, linkedin, sections, size)
    if extension == 'docx':
        return _docx(candidate['full_name'], contact, linkedin, sections, size)
    raise ValueError('PDF_OR_DOCX_REQUIRED')


def _fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    regular, bold = _font_files()
    for font_name, path in (('RadarCV', regular), ('RadarCVBold', bold)):
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, path))
    from reportlab.lib.fonts import addMapping
    addMapping('RadarCV', 0, 0, 'RadarCV')
    addMapping('RadarCV', 1, 0, 'RadarCVBold')


def _emphasis(label, text, index):
    """Format exact substrings only. No generated summaries or reference claims."""
    if label == 'Experience' and index == 0 and len(text) < 220:
        return text, ''
    if label in {'Core Capabilities', 'Selected Projects', 'Education & Training', 'Additional Experience'}:
        prefix, separator, suffix = text.partition(':')
        if separator:
            return prefix + separator, suffix
    return '', text


def _story(name, contact, linkedin, sections, size):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Paragraph, Spacer, HRFlowable, KeepTogether
    navy = HexColor('#' + REFERENCE.navy)
    body = ParagraphStyle('CVBody', fontName='RadarCV', fontSize=size,
                          leading=size*1.22, spaceAfter=3, textColor=HexColor('#252525'))
    title = ParagraphStyle('CVName', parent=body, fontName='RadarCVBold', textColor=navy,
                           fontSize=REFERENCE.name_size, leading=26, spaceAfter=3)
    small = ParagraphStyle('CVContact', parent=body, fontSize=REFERENCE.contact_size,
                           leading=10.5, spaceAfter=1, textColor=HexColor('#' + REFERENCE.muted))
    heading = ParagraphStyle('CVSection', parent=body, fontName='RadarCVBold', textColor=navy,
                             fontSize=REFERENCE.heading_size, leading=12, spaceBefore=8,
                             spaceAfter=2, keepWithNext=True)
    paragraph = lambda text, style: Paragraph(escape(text).replace('\n', '<br/>'), style)
    story = [paragraph(name, title), HRFlowable(width='100%', thickness=1.8, color=navy,
                                               spaceBefore=0, spaceAfter=4), paragraph(contact, small)]
    if linkedin:
        story.append(paragraph(linkedin, small))
    story.append(Spacer(1, 2))
    for label, claims in sections:
        rule = HRFlowable(width='100%', thickness=.6, color=HexColor('#' + REFERENCE.rule),
                           spaceBefore=0, spaceAfter=4)
        story.append(KeepTogether([paragraph(label.upper(), heading), rule]))
        for index, text in enumerate(claims):
            style = body
            if label == 'Professional Profile':
                style = ParagraphStyle('CVProfile', parent=body, backColor=HexColor('#' + REFERENCE.panel),
                                       borderColor=navy, borderWidth=.8, borderPadding=5, spaceAfter=4)
            elif label == 'Experience' and index > 0:
                style = ParagraphStyle('CVBullet', parent=body, leftIndent=10, firstLineIndent=0,
                                       bulletIndent=0)
            bold, rest = _emphasis(label, text, index)
            markup = '<b>' + escape(bold) + '</b>' + escape(rest) if bold else escape(rest)
            story.append(Paragraph(markup.replace('\n', '<br/>'), style,
                                   bulletText='\u2022' if label == 'Experience' and index > 0 else None))
    return story


def _fit_size(name, contact, linkedin, sections):
    _fonts()
    for size in (REFERENCE.body_size, 9):
        raw = _pdf(name, contact, linkedin, sections, size)
        from pypdf import PdfReader
        if len(PdfReader(io.BytesIO(raw)).pages) == 1:
            return size
    raise ValueError('CV_CONTENT_EXCEEDS_ONE_PAGE_REVIEW_REQUIRED')


def _pdf(name, contact, linkedin, sections, size):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
    from reportlab.platypus.doctemplate import LayoutError
    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, leftMargin=REFERENCE.margin,
                            rightMargin=REFERENCE.margin, topMargin=REFERENCE.top,
                            bottomMargin=REFERENCE.bottom, title='Curriculum vitae', author='',
                            creator='Cork Job Radar ' + LAYOUT_VERSION)
    # Explicit frame avoids the default 6 pt inset in SimpleDocTemplate.
    frame = Frame(REFERENCE.margin, REFERENCE.bottom, A4[0] - 2*REFERENCE.margin,
                  A4[1] - REFERENCE.top - REFERENCE.bottom,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id='Reference', frames=[frame]))
    try:
        doc.build(_story(name, contact, linkedin, sections, size), canvasmaker=_deterministic_canvas)
    except LayoutError:
        raise ValueError('CV_CONTENT_EXCEEDS_ONE_PAGE_REVIEW_REQUIRED') from None
    return buffer.getvalue()


def _deterministic_canvas(*args, **kwargs):
    from reportlab.pdfgen.canvas import Canvas
    kwargs['invariant'] = 1
    return Canvas(*args, **kwargs)


def _docx(name, contact, linkedin, sections, size):
    from docx import Document
    from docx.shared import Pt, Mm, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc = Document()
    page = doc.sections[0]
    page.page_width, page.page_height = Mm(210), Mm(297)
    page.left_margin = page.right_margin = Pt(REFERENCE.margin)
    page.top_margin, page.bottom_margin = Pt(REFERENCE.top), Pt(REFERENCE.bottom)
    normal = doc.styles['Normal']
    normal.font.name, normal.font.size = 'Arial', Pt(size)
    normal.paragraph_format.space_after = Pt(3)
    normal.paragraph_format.line_spacing = Pt(size*1.22)
    for style_name, font_size in (('Title', REFERENCE.name_size), ('Heading 1', REFERENCE.heading_size)):
        style = doc.styles[style_name]
        style.font.name, style.font.size = 'Arial', Pt(font_size)
        style.font.color.rgb = RGBColor.from_string(REFERENCE.navy)
        style.font.bold = True
        style.paragraph_format.space_after = Pt(4)
    doc.styles['Heading 1'].paragraph_format.space_before = Pt(8)
    doc.styles['Heading 1'].paragraph_format.keep_with_next = True
    doc.styles['Heading 1'].font.all_caps = True
    doc.styles['Title'].paragraph_format.space_before = Pt(0)
    doc.styles['Title'].paragraph_format.line_spacing = Pt(26)
    for style_name in ('Normal', 'Title', 'Heading 1', 'List Bullet'):
        fonts = doc.styles[style_name].element.get_or_add_rPr().get_or_add_rFonts()
        # Theme attributes in Word's built-in styles can override font.name in
        # LibreOffice/Word, producing Calibri instead of the reference Arial.
        for attr in list(fonts.attrib):
            if attr.rsplit('}', 1)[-1].lower().endswith('theme'):
                del fonts.attrib[attr]
        for attr in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
            fonts.set(qn('w:' + attr), 'Arial')
    # Word's built-in Title style can inherit a decorative blue paragraph rule.
    for style in doc.styles:
        for border in list(style.element.iter(qn('w:pBdr'))):
            border.getparent().remove(border)
    def border(paragraph, side, color, thickness):
        borders = OxmlElement('w:pBdr')
        line = OxmlElement('w:' + side)
        for key, value in {'val':'single', 'sz':str(thickness), 'color':color, 'space':'3'}.items():
            line.set(qn('w:' + key), value)
        borders.append(line)
        paragraph._p.get_or_add_pPr().append(borders)

    title = doc.add_paragraph(name, style='Title')
    border(title, 'bottom', REFERENCE.navy, 14)
    title.paragraph_format.keep_with_next = True
    for text in (contact, linkedin):
        if text:
            p = doc.add_paragraph(text)
            for run in p.runs:
                run.font.size = Pt(REFERENCE.contact_size)
                run.font.color.rgb = RGBColor.from_string(REFERENCE.muted)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = Pt(10.5)
    for label, claims in sections:
        heading = doc.add_paragraph(label, style='Heading 1')
        border(heading, 'bottom', REFERENCE.rule, 4)
        for index, text in enumerate(claims):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = Pt(size*1.22)
            bold, rest = _emphasis(label, text, index)
            if bold:
                p.add_run(bold).bold = True
            p.add_run(rest)
            if label == 'Experience' and index > 0:
                # Real Word bullets, with no floating objects or text boxes.
                p.style = doc.styles['List Bullet']
                p.paragraph_format.left_indent = Pt(10)
                p.paragraph_format.first_line_indent = Pt(-10)
            if label == 'Professional Profile':
                shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), REFERENCE.panel)
                p._p.get_or_add_pPr().append(shade)
                border(p, 'left', REFERENCE.navy, 14)
    doc.core_properties.author = ''
    doc.core_properties.last_modified_by = ''
    doc.core_properties.title = 'Curriculum vitae'
    doc.core_properties.subject = LAYOUT_VERSION
    buffer = io.BytesIO()
    doc.save(buffer)
    # ZIP entry timestamps otherwise create a different draft on every render.
    import zipfile
    stable = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as source, zipfile.ZipFile(stable, 'w', zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            entry.date_time = (1980, 1, 1, 0, 0, 0)
            target.writestr(entry, source.read(entry.filename))
    return stable.getvalue()
