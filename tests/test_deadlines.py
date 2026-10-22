from datetime import datetime
from zoneinfo import ZoneInfo
from corkjobradar.verification import deadline_state,evidence_status
from corkjobradar.autoapply.eligibility import evaluate_autoapply
from test_autoapply_policy import inputs


def test_explicit_deadline_closes_at_its_time_not_next_day():
    clock=datetime(2026,10,19,16,0,tzinfo=ZoneInfo('Europe/Dublin'))
    job={'title':'Synthetic','description':'Synthetic complete description','detail_complete':True,
         'raw':{'validThrough':'2026-10-19T14:00:00Z'}}
    assert evidence_status(job,clock)[0]=='CLOSED_CONFIRMED'
    job['raw']['validThrough']='2026-10-19'
    assert evidence_status(job,clock)[0]=='OPEN_LIKELY'
    assert deadline_state({'validThrough':'2026-10-19T18:00:00+01:00'},clock)[0]=='NOT_EXPIRED'


def test_missing_zone_and_dst_ambiguity_never_invent_an_instant():
    assert deadline_state({'application_deadline':'2026-10-19T15:00:00'})[0]=='UNKNOWN_TIMEZONE'
    assert deadline_state({'application_deadline':'2026-10-25T01:30:00','deadline_timezone':'Europe/Dublin'})[0]=='AMBIGUOUS_LOCAL_TIME'
    assert deadline_state({'application_deadline':'not a date'})[0]=='UNPARSEABLE'


def test_autoapply_blocks_expired_same_day_and_holds_ambiguous_date(profile):
    data=inputs(profile)
    data['job']['raw']={'validThrough':'2026-10-19T09:00:00+01:00'}
    assert evaluate_autoapply(**data).outcome=='BLOCK'
    data['job']['raw']={'validThrough':'2026-10-19T09:00:00'}
    assert 'DEADLINE_NOT_VERIFIABLE' in [r.code for r in evaluate_autoapply(**data).reasons]
