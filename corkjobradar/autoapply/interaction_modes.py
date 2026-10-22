"""Provider restrictions are independent of the source of a job link."""
import re
from urllib.parse import urlsplit,urlunsplit,parse_qs,urlencode
from .platforms import platform_for

LINKEDIN_MANUAL='LINKEDIN_MANUAL'
INDEED_MANUAL='INDEED_MANUAL'
EMPLOYER_SITE_ALLOWED='EMPLOYER_SITE_ALLOWED'
HUMAN_VERIFICATION='HUMAN_VERIFICATION'
HOLD='HOLD'


def provider(url):
    try:
        p=urlsplit(url);host=(p.hostname or '').lower()
        if p.scheme!='https' or p.username or p.password or p.port not in {None,443}:return 'invalid'
    except (TypeError,ValueError):return 'invalid'
    if host=='linkedin.com' or host.endswith('.linkedin.com'):return 'linkedin'
    if host=='indeed.com' or host.endswith('.indeed.com') or host=='indeed.ie' or host.endswith('.indeed.ie'):return 'indeed'
    # International Indeed domains are explicit, not a substring match.
    if any(host==d or host.endswith('.'+d) for d in ('indeed.co.uk','indeed.fr','indeed.es','indeed.de','indeed.ca','indeed.com.au','indeed.co.in')):return 'indeed'
    if not host or p.query or p.fragment:return 'invalid'
    return 'employer'


def interaction_route(url,*,source_url=None,human_verification=False):
    kind=provider(url)
    base={'automation_allowed':False,'independent_employer_review_required':False,'live_enabled':False}
    if kind=='linkedin':return {**base,'mode':LINKEDIN_MANUAL,'reason':'LINKEDIN_AUTOMATION_PROHIBITED'}
    if kind=='indeed':return {**base,'mode':INDEED_MANUAL,'reason':'INDEED_UNOFFICIAL_APPLY_AUTOMATION_PROHIBITED'}
    if kind!='employer':return {**base,'mode':HOLD,'reason':'CLEAN_HTTPS_DESTINATION_REQUIRED'}
    cap=platform_for(url)
    # A portal's redirect never grants rights at the employer. Capabilities are
    # reviewed independently for that destination; currently none are released.
    reviewed=bool(cap.get('automation_permitted') and cap.get('verified') and cap.get('hosted_form_verified'))
    independent=bool(source_url and source_url!=url)
    if not reviewed:return {**base,'mode':HOLD,'reason':'INDEPENDENT_EMPLOYER_PERMISSION_AND_FORM_REQUIRED',
                            'independent_employer_review_required':independent}
    return {**base,'mode':HUMAN_VERIFICATION if human_verification else EMPLOYER_SITE_ALLOWED,
            'reason':'HUMAN_CHECK_REQUIRED' if human_verification else 'REVIEWED_EMPLOYER_FORM',
            'automation_allowed':True,'independent_employer_review_required':independent}


def manual_target_url(url):
    """Keep reviewed public job IDs for manual links; never grant automation."""
    kind=provider(url);p=urlsplit(url)
    if kind=='invalid' and p.scheme=='https' and p.hostname and not p.username and not p.password and p.port in {None,443}:
        values=parse_qs(p.query).get('gh_jid',[])
        if values:
            if len(set(values))!=1 or not re.fullmatch(r'\d{1,20}',values[0]):raise ValueError('AMBIGUOUS_GREENHOUSE_JOB_IDENTIFIER')
            # Employer-hosted Greenhouse adverts need this numeric ID. Other
            # query values (tracking/session secrets) are never copied.
            return urlunsplit(('https',p.netloc,p.path,urlencode({'gh_jid':values[0]}),''))
    if kind=='invalid' or p.username or p.password:raise ValueError('CLEAN_HTTPS_APPLICATION_URL_REQUIRED')
    if kind=='indeed':
        query=parse_qs(p.query)
        job=query.get('jk',[])
        if p.path=='/viewjob' and len(job)==1 and re.fullmatch('[a-fA-F0-9]{10,40}',job[0]):
            return urlunsplit(('https',p.netloc,p.path,urlencode({'jk':job[0]}),''))
        if p.query or p.fragment:raise ValueError('EXACT_INDEED_JOB_LINK_REQUIRED')
    elif kind=='linkedin':
        if p.query or p.fragment:
            if not re.fullmatch(r'/jobs/view/[^/]+/?',p.path):raise ValueError('EXACT_LINKEDIN_JOB_LINK_REQUIRED')
            return urlunsplit(('https',p.netloc,p.path,'',''))
    elif p.query or p.fragment:raise ValueError('CLEAN_HTTPS_APPLICATION_URL_REQUIRED')
    return url
