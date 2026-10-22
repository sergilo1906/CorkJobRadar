import csv
import io
import zipfile
from datetime import datetime
import pytest
from corkjobradar.transit import import_gtfs,Transit,seconds


def make_feed(path):
    # All values below are SYNTHETIC ONLY; never imported into production storage.
    files={
      'feed_info.txt':[['feed_publisher_name','feed_start_date','feed_end_date'],['SYNTHETIC TEST ONLY','20261001','20261231']],
      'stops.txt':[['stop_id','stop_name','stop_lat','stop_lon'],['a','Fixture A',51.88,-8.44],['b','Fixture B',51.89,-8.47]],
      'routes.txt':[['route_id','route_short_name','route_long_name','route_type'],['r','TEST','SYNTHETIC ONLY','3']],
      'trips.txt':[['route_id','service_id','trip_id'],['r','week','out'],['r','week','back'],['r','night','night']],
      'stop_times.txt':[['trip_id','arrival_time','departure_time','stop_id','stop_sequence'],
        ['out','08:00:00','08:00:00','a',1],['out','08:20:00','08:20:00','b',2],
        ['back','17:20:00','17:20:00','b',1],['back','17:40:00','17:40:00','a',2],
        ['night','25:10:00','25:10:00','b',1],['night','25:30:00','25:30:00','a',2]],
      'calendar.txt':[['service_id','monday','tuesday','wednesday','thursday','friday','saturday','sunday','start_date','end_date'],
        ['week',1,1,1,1,1,0,0,'20261001','20261231'],['night',1,0,0,0,0,0,0,'20261001','20261231']],
      'calendar_dates.txt':[['service_id','date','exception_type'],['week','20261020',2]]}
    with zipfile.ZipFile(path,'w') as archive:
        for name,rows in files.items():
            text=io.StringIO();csv.writer(text).writerows(rows);archive.writestr(name,text.getvalue())


@pytest.fixture
def transit(tmp_path):
    path=tmp_path/'fixture.zip';make_feed(path);target=tmp_path/'transit.sqlite3'
    stats=import_gtfs(path,{'url':'https://fixture.test/GTFS'},target)
    assert stats['stops']==2 and stats['stop_times']==6
    assert import_gtfs(path,{'url':'https://fixture.test/GTFS'},target)==stats
    return Transit(target)


def test_both_directions_zero_transfers_and_exception(transit):
    plan=transit.shift_plan('a','b','b','a',datetime(2026,10,19,9),datetime(2026,10,19,17),5,5)
    assert plan['outbound_count']==plan['return_count']==1
    assert plan['outbound'][0]['transfers']==0
    removed=transit.shift_plan('a','b','b','a',datetime(2026,10,20,9),datetime(2026,10,20,17),5,5)
    assert removed['status']=='SIN_IDA_VUELTA_EN_DATOS'
    assert 'no exista transporte' in removed['limitation']


def test_door_to_door_calculation_includes_access_and_return_wait(transit):
    plan=transit.shift_plan('a','b','b','a',datetime(2026,10,19,9),datetime(2026,10,19,17),7,11)
    outward=plan['outbound'][0];returning=plan['return'][0]
    assert outward['origin_departure']=='2026-10-19T07:53:00'
    assert outward['work_arrival']=='2026-10-19T08:31:00'
    assert outward['door_to_door_minutes']==38
    assert outward['margin_before_shift_minutes']==29
    assert returning['origin_arrival']=='2026-10-19T17:47:00'
    assert returning['door_to_door_minutes']==47
    assert returning['wait_at_stop_minutes']==9
    assert 'NO_VERIFICADOS' in outward['access_evidence']
    assert 'mismo valor para cada sentido' in plan['limitation']


def test_after_midnight_previous_service_day(transit):
    trips=transit.direct('b','a',datetime(2026,10,20,1),datetime(2026,10,20,2))
    assert trips[0]['service_date']=='2026-10-19' and trips[0]['arrival']=='2026-10-20T01:30:00'
    assert seconds('25:30:00')==91800


def test_expired_data_and_dst_cannot_claim_route(transit):
    with pytest.raises(ValueError,match='vigencia'):
        transit.direct('a','b',datetime(2027,1,1),datetime(2027,1,1,12))
    with pytest.raises(ValueError,match='cambio de hora'):
        transit.direct('a','b',datetime(2026,10,25),datetime(2026,10,25,12))
