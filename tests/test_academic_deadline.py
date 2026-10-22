from datetime import datetime
import pytest
from corkjobradar.verification import deadline_state


@pytest.mark.parametrize('description,status',[
    ('Closing date: 23rd October 2026.','NOT_EXPIRED'),
    ('<p>Closing date: 23rd October 2026.</p>','NOT_EXPIRED'),
    ('Closing date: 23rd October.','UNPARSEABLE'),
    ('Closing date: 31st February 2026.','UNPARSEABLE'),
    ('Closing date: 23rd October 2026.\nClosing date: 24th October 2026.','UNPARSEABLE'),
    ('Degree completed by November 2026.','ABSENT'),
])
def test_explicit_description_deadline_is_not_silently_absent(description,status):
    assert deadline_state({'descriptionPlain':description},datetime.fromisoformat('2026-10-22T12:00:00+01:00'))[0]==status


def test_ats_description_deadline_expires_without_relying_on_form_still_being_visible():
    raw={'descriptionPlain':'Closing date: 23rd October 2026.'}
    assert deadline_state(raw,datetime.fromisoformat('2026-10-23T23:59:59+01:00'))[0]=='NOT_EXPIRED'
    assert deadline_state(raw,datetime.fromisoformat('2026-10-24T00:00:00+01:00'))[0]=='EXPIRED'
