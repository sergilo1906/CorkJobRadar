"""Artificial timetable, explicitly isolated from production GTFS."""
from datetime import datetime
from copy import deepcopy
import pytest
from test_transit import transit
from corkjobradar.geography import valid_commute
from test_autoapply_policy import inputs


ACCESS={'home_to_out_stop':7,'out_stop_to_work':11,'work_to_back_stop':3,'back_stop_to_home':9}


def test_asymmetric_return_access_and_all_dates_with_holiday(transit):
    shifts=[{'start':f'2026-10-{d}T09:00:00','end':f'2026-10-{d}T17:00:00'} for d in (19,20,21)]
    result=transit.shift_schedule('a','b','b','a',shifts,ACCESS)
    assert result['checked_shift_count']==3
    assert [s['scheduled_round_trip_found'] for s in result['shifts']]==[True,False,True]
    assert result['status']=='HOLD' and not result['route_autoapproved'] and not result['car_assumed']
    back=result['shifts'][0]['plan']['return'][0]
    assert back['origin_arrival']=='2026-10-19T17:49:00'
    assert back['door_to_door_minutes']==49 and back['wait_at_stop_minutes']==17


def test_limit_includes_waiting_and_access(transit):
    shift=[{'start':'2026-10-19T09:00:00','end':'2026-10-19T17:00:00'}]
    assert transit.shift_schedule('a','b','b','a',shift,ACCESS,max_minutes=40)['status']=='HOLD'
    assert transit.shift_schedule('a','b','b','a',shift,ACCESS,max_minutes=50)['status']=='SCHEDULED_ALL_REQUESTED_SHIFTS'


@pytest.mark.parametrize('invalid',[float('nan'),float('inf'),-1,True,'5'])
def test_non_numeric_or_unbounded_access_never_validates(transit,invalid):
    with pytest.raises(ValueError):transit.shift_plan('a','b','b','a',datetime(2026,10,19,9),datetime(2026,10,19,17),invalid,5)


def test_dst_and_dates_outside_feed_are_retained_individually(transit):
    shifts=[{'start':'2026-10-25T09:00:00','end':'2026-10-25T17:00:00'},
            {'start':'2027-01-01T09:00:00','end':'2027-01-01T17:00:00'}]
    result=transit.shift_schedule('a','b','b','a',shifts,ACCESS)
    assert result['status']=='HOLD' and len(result['shifts'])==2
    assert all(s['hold_reason'] for s in result['shifts'])


@pytest.mark.parametrize('patch',[{'valid_until':'invalid'},{'shift_compatible':'yes'},{'duration_minutes':float('nan')},{'duration_minutes':True}])
def test_ambiguous_manual_route_never_authorizes(profile,patch):
    check=deepcopy(inputs(profile)['transport'][0]);check['details'].update(patch)
    assert not valid_commute(check,profile)
