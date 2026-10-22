"""Direct, scheduled bus journeys. Access/egress and job shifts require user evidence."""
import csv
import hashlib
import io
import json
import math
import sqlite3
import zipfile
from datetime import datetime,timedelta,time as daytime
from pathlib import Path
from zoneinfo import ZoneInfo
from .config import ROOT,now

TRANSIT_PATH=ROOT/'data/transport.sqlite3'
SOURCE_URL='https://www.transportforireland.ie/transitData/Data/GTFS_Bus_Eireann.zip'
ATTRIBUTION='GTFS Data © 2025 NTA, CC BY 4.0. Datos proporcionados tal cual; NTA no responde de errores. Horarios programados, sin tiempo real.'
SCHEMA='''
CREATE TABLE IF NOT EXISTS feeds(id TEXT PRIMARY KEY,imported_at TEXT,source_url TEXT,metadata TEXT,stats TEXT);
CREATE TABLE IF NOT EXISTS stops(feed TEXT,id TEXT,name TEXT,lat REAL,lon REAL,PRIMARY KEY(feed,id));
CREATE TABLE IF NOT EXISTS routes(feed TEXT,id TEXT,name TEXT,PRIMARY KEY(feed,id));
CREATE TABLE IF NOT EXISTS trips(feed TEXT,id TEXT,route TEXT,service TEXT,headsign TEXT,PRIMARY KEY(feed,id));
CREATE TABLE IF NOT EXISTS times(feed TEXT,trip TEXT,stop TEXT,sequence INTEGER,arrival INTEGER,departure INTEGER,pickup TEXT,dropoff TEXT);
CREATE INDEX IF NOT EXISTS times_stop ON times(feed,stop,trip);
CREATE TABLE IF NOT EXISTS calendars(feed TEXT,id TEXT,start TEXT,end TEXT,weekdays TEXT,PRIMARY KEY(feed,id));
CREATE TABLE IF NOT EXISTS exceptions(feed TEXT,service TEXT,date TEXT,kind INTEGER);
'''


def seconds(value):
    parts=value.split(':')
    if len(parts)!=3:
        raise ValueError('Hora GTFS vacía/no interpretable')
    h,m,s=map(int,parts)
    if h<0 or not 0<=m<60 or not 0<=s<60:
        raise ValueError('Hora GTFS inválida')
    return h*3600+m*60+s


def refresh_bus_data():
    from .http import WebClient
    from .config import load_profile
    path=ROOT/'data/GTFS_Bus_Eireann.zip';meta=ROOT/'data/GTFS_Bus_Eireann-provenance.json'
    previous=json.loads(meta.read_text(encoding='utf-8')) if meta.exists() else {}
    if not path.exists() or not previous.get('fetched_at','').startswith(now()[:10]):
        profile=load_profile();profile.update(max_response_bytes=60_000_000,http_retries=0)
        with WebClient(profile) as client:
            response=client.get(SOURCE_URL,check_robots=True,accept='application/zip')
        temporary=path.with_suffix('.part');temporary.write_bytes(response.content)
        with zipfile.ZipFile(temporary) as bundle:
            if not {'stops.txt','trips.txt','stop_times.txt'}.issubset(bundle.namelist()):
                raise ValueError('Respuesta GTFS sin archivos de horarios')
        temporary.replace(path)
        previous={'url':SOURCE_URL,'fetched_at':now(),'sha256':hashlib.sha256(response.content).hexdigest(),
                  'last_modified':response.headers.get('last-modified'),'licence':'CC BY 4.0',
                  'attribution':ATTRIBUTION,'policy':'https://developer.nationaltransport.ie/usagepolicy'}
        meta.write_text(json.dumps(previous,ensure_ascii=False,indent=2),encoding='utf-8')
    return import_gtfs(path,previous)


def import_gtfs(path,provenance,db_path=TRANSIT_PATH,bounds=(51.7,52.1,-8.9,-8.0)):
    """Stream CSVs; store only stops within explicit Cork bounding rectangle.

    No shapes required: scheduled direct trips don't establish walking/cycling routes.
    Failed imports roll back, keeping all previous feeds usable.
    """
    path=Path(path)
    bounds=list(bounds)
    with path.open('rb') as handle:
        fid=hashlib.file_digest(handle,'sha256').hexdigest()
    con=sqlite3.connect(db_path,timeout=30);con.executescript(SCHEMA)
    try:
        if con.execute('SELECT 1 FROM feeds WHERE id=?',(fid,)).fetchone():
            return json.loads(con.execute('SELECT stats FROM feeds WHERE id=?',(fid,)).fetchone()[0])
        with zipfile.ZipFile(path) as bundle, con:
            if sum(x.file_size for x in bundle.infolist())>1_000_000_000:
                raise ValueError('GTFS descomprimido excede 1 GB')
            def rows(name,required=True):
                if name not in bundle.namelist():
                    if required:
                        raise ValueError('Falta archivo GTFS '+name)
                    return
                with bundle.open(name) as raw,io.TextIOWrapper(raw,encoding='utf-8-sig',newline='') as text:
                    yield from csv.DictReader(text)
            info=list(rows('feed_info.txt',False));metadata={'provenance':provenance,'feed_info':info,'bounds':bounds,'attribution':ATTRIBUTION}
            stops=set()
            for r in rows('stops.txt'):
                lat,lon=float(r['stop_lat']),float(r['stop_lon'])
                if bounds[0]<=lat<=bounds[1] and bounds[2]<=lon<=bounds[3]:
                    stops.add(r['stop_id']);con.execute('INSERT INTO stops VALUES(?,?,?,?,?)',(fid,r['stop_id'],r['stop_name'],lat,lon))
            selected_trips=set();count=0;unreadable=0;batch=[]
            for r in rows('stop_times.txt'):
                if r['stop_id'] not in stops:
                    continue
                selected_trips.add(r['trip_id'])
                try:
                    arr,dep=seconds(r['arrival_time']),seconds(r['departure_time'])
                except ValueError:
                    unreadable+=1;continue
                batch.append((fid,r['trip_id'],r['stop_id'],int(r['stop_sequence']),arr,dep,r.get('pickup_type') or '0',r.get('drop_off_type') or '0'));count+=1
                if len(batch)>=5000:
                    con.executemany('INSERT INTO times VALUES(?,?,?,?,?,?,?,?)',batch);batch.clear()
            con.executemany('INSERT INTO times VALUES(?,?,?,?,?,?,?,?)',batch)
            used_routes=set();trip_count=0
            for r in rows('trips.txt'):
                if r['trip_id'] in selected_trips:
                    con.execute('INSERT INTO trips VALUES(?,?,?,?,?)',(fid,r['trip_id'],r['route_id'],r['service_id'],r.get('trip_headsign','')))
                    used_routes.add(r['route_id']);trip_count+=1
            for r in rows('routes.txt'):
                if r['route_id'] in used_routes:
                    if r['route_type'] not in {'3','700','701','702','703','704','705','706','707','708','709','710','711','712','713','714','715','716'}:
                        raise ValueError('Este importador solo admite servicios de autobús')
                    con.execute('INSERT INTO routes VALUES(?,?,?)',(fid,r['route_id'],(r.get('route_short_name','')+' '+r.get('route_long_name','')).strip()))
            for r in rows('calendar.txt',False):
                days=''.join(r[d] for d in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'])
                con.execute('INSERT INTO calendars VALUES(?,?,?,?,?)',(fid,r['service_id'],r['start_date'],r['end_date'],days))
            for r in rows('calendar_dates.txt',False):
                con.execute('INSERT INTO exceptions VALUES(?,?,?,?)',(fid,r['service_id'],r['date'],int(r['exception_type'])))
            stats={'feed':fid,'stops':len(stops),'trips':trip_count,'stop_times':count,'unreadable_times':unreadable,
                   'bounds':bounds,'feed_info':info,'source_url':provenance['url'],'attribution':ATTRIBUTION}
            con.execute('INSERT INTO feeds VALUES(?,?,?,?,?)',(fid,now(),provenance['url'],json.dumps(metadata,ensure_ascii=False),json.dumps(stats,ensure_ascii=False)))
            return stats
    finally:
        con.close()


class Transit:
    def __init__(self,path=TRANSIT_PATH):
        if not Path(path).exists():
            raise ValueError('Sin GTFS importado; usar comprobación manual asistida')
        self.path=path

    def rows(self,sql,params=()):
        with sqlite3.connect(self.path,timeout=30) as con:
            con.row_factory=sqlite3.Row
            return [dict(r) for r in con.execute(sql,params)]

    def latest(self):
        feeds=self.rows('SELECT * FROM feeds ORDER BY imported_at DESC,rowid DESC LIMIT 1')
        if not feeds:
            raise ValueError('No hay una importación GTFS válida')
        return feeds[0]

    def stops(self,query=''):
        feed=self.latest()['id']
        return self.rows('SELECT * FROM stops WHERE feed=? AND (name LIKE ? OR id=?) ORDER BY name,id',(feed,'%'+query+'%',query))

    def active_services(self,feed,day):
        stamp=day.strftime('%Y%m%d');weekday=day.weekday()
        active={r['id'] for r in self.rows('SELECT * FROM calendars WHERE feed=? AND start<=? AND end>=?',(feed,stamp,stamp)) if r['weekdays'][weekday]=='1'}
        for r in self.rows('SELECT * FROM exceptions WHERE feed=? AND date=?',(feed,stamp)):
            active.add(r['service']) if r['kind']==1 else active.discard(r['service'])
        return active

    def direct(self,origin,destination,earliest,latest):
        """Every exact direct trip within the requested local time window; zero transfers."""
        if earliest.tzinfo or latest.tzinfo or earliest>latest:
            raise ValueError('Usar intervalo local de Europe/Dublin sin zona incorporada y ordenado')
        feed=self.latest();info=json.loads(feed['metadata']).get('feed_info',[])
        if not info or not info[0].get('feed_start_date') or not info[0].get('feed_end_date'):
            raise ValueError('Vigencia del feed no publicada; revisión manual requerida')
        start,end=info[0]['feed_start_date'],info[0]['feed_end_date']
        for day in [earliest.date(),latest.date()]:
            if not start<=day.strftime('%Y%m%d')<=end:
                raise ValueError('Fecha solicitada fuera de vigencia publicada del GTFS')
            zone=ZoneInfo('Europe/Dublin')
            if datetime.combine(day,daytime(0),zone).utcoffset()!=datetime.combine(day,daytime(12),zone).utcoffset():
                raise ValueError('Día de cambio de hora: comprobación manual requerida')
        records=self.rows('''SELECT a.trip,a.departure,b.arrival,t.service,t.headsign,r.name route
            FROM times a JOIN times b ON a.feed=b.feed AND a.trip=b.trip AND b.sequence>a.sequence
            JOIN trips t ON t.feed=a.feed AND t.id=a.trip JOIN routes r ON r.feed=t.feed AND r.id=t.route
            WHERE a.feed=? AND a.stop=? AND b.stop=? AND a.pickup='0' AND b.dropoff='0' ''',(feed['id'],origin,destination))
        result=[];service_day=earliest.date()-timedelta(days=1)
        while service_day<=latest.date():
            active=self.active_services(feed['id'],service_day);midnight=datetime.combine(service_day,daytime())
            for row in records:
                if row['service'] not in active:
                    continue
                departure=midnight+timedelta(seconds=row['departure']);arrival=midnight+timedelta(seconds=row['arrival'])
                if departure>=earliest and arrival<=latest and arrival>=departure:
                    result.append({'trip':row['trip'],'route':row['route'],'headsign':row['headsign'],
                                   'departure':departure.isoformat(),'arrival':arrival.isoformat(),'origin_stop':origin,
                                   'destination_stop':destination,'transfers':0,'service_date':service_day.isoformat()})
            service_day+=timedelta(days=1)
        return sorted(result,key=lambda r:r['departure'])

    def shift_plan(self,origin_out,destination_out,origin_back,destination_back,start,end,walk_origin,walk_destination,buffer=10,window=120,*,walk_work_return=None,walk_home_return=None):
        walk_work_return=walk_destination if walk_work_return is None else walk_work_return
        walk_home_return=walk_origin if walk_home_return is None else walk_home_return
        values=(walk_origin,walk_destination,buffer,window,walk_work_return,walk_home_return)
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1440 for v in values):
            raise ValueError('Tiempos de acceso finitos y no negativos requeridos')
        if start.tzinfo or end.tzinfo or end<=start or end-start>timedelta(hours=24) or window==0:
            raise ValueError('Turno o tiempos de acceso inválidos')
        outward=self.direct(origin_out,destination_out,start-timedelta(minutes=window),start-timedelta(minutes=walk_destination+buffer))
        returning=self.direct(origin_back,destination_back,end+timedelta(minutes=walk_work_return),end+timedelta(minutes=walk_work_return+window))
        for journey in outward:
            departure=datetime.fromisoformat(journey['departure']);arrival=datetime.fromisoformat(journey['arrival'])
            door_departure=departure-timedelta(minutes=walk_origin);door_arrival=arrival+timedelta(minutes=walk_destination)
            journey.update(origin_departure=door_departure.isoformat(),work_arrival=door_arrival.isoformat(),
                           door_to_door_minutes=(door_arrival-door_departure).total_seconds()/60,
                           margin_before_shift_minutes=(start-door_arrival).total_seconds()/60,
                           access_evidence='TIEMPOS_A_PIE_DECLARADOS_POR_EL_USUARIO_NO_VERIFICADOS_POR_GTFS')
        for journey in returning:
            departure=datetime.fromisoformat(journey['departure']);arrival=datetime.fromisoformat(journey['arrival'])
            # Starting at shift end includes the actual wait for the selected bus.
            home_arrival=arrival+timedelta(minutes=walk_home_return)
            journey.update(work_departure=end.isoformat(),origin_arrival=home_arrival.isoformat(),
                           door_to_door_minutes=(home_arrival-end).total_seconds()/60,
                           wait_at_stop_minutes=(departure-end).total_seconds()/60-walk_work_return,
                           access_evidence='TIEMPOS_A_PIE_DECLARADOS_POR_EL_USUARIO_NO_VERIFICADOS_POR_GTFS')
        return {'outbound':outward,'return':returning,'outbound_count':len(outward),'return_count':len(returning),
                'status':'HORARIO_DIRECTO_IDA_VUELTA_ENCONTRADO' if outward and returning else 'SIN_IDA_VUELTA_EN_DATOS',
                'shift_start':start.isoformat(),'shift_end':end.isoformat(),'walk_origin_minutes_declared':walk_origin,
                'walk_destination_minutes_declared':walk_destination,'buffer_minutes':buffer,
                'walk_work_return_minutes_declared':walk_work_return,'walk_home_return_minutes_declared':walk_home_return,
                'feed':self.latest()['id'],'source_url':self.latest()['source_url'],'checked_at':now(),'attribution':ATTRIBUTION,
                'limitation':'Solo Bus Éireann y paradas del rectángulo Cork importado. Los tiempos totales usan los accesos a pie declarados; por defecto el mismo valor para cada sentido, salvo cuatro accesos explícitos. No son rutas a pie verificadas. Accesos, parada de vuelta, centro, días y turno requieren confirmación. Ausencia no demuestra que no exista transporte.'}

    def shift_schedule(self,origin_out,destination_out,origin_back,destination_back,shifts,access,*,buffer=10,window=120,max_minutes=None):
        """Check EVERY explicit shift, including exceptions and overnight returns.

        This is scheduled bus evidence, never automatic approval of walking legs,
        a workplace, an unknown rota or accessibility on unrequested dates.
        """
        if not isinstance(shifts,list) or not 1<=len(shifts)<=31:raise ValueError('Entre 1 y 31 turnos explícitos requeridos')
        keys={'home_to_out_stop','out_stop_to_work','work_to_back_stop','back_stop_to_home'}
        if not isinstance(access,dict) or set(access)!=keys:raise ValueError('Cuatro accesos separados requeridos')
        if max_minutes is not None and (isinstance(max_minutes,bool) or not isinstance(max_minutes,(int,float)) or not math.isfinite(max_minutes) or max_minutes<=0):raise ValueError('Límite total de viaje inválido')
        result=[];seen=set()
        for shift in shifts:
            if not isinstance(shift,dict) or set(shift)!={'start','end'}:raise ValueError('Cada turno requiere entrada y salida explícitas')
            start=datetime.fromisoformat(shift['start']);end=datetime.fromisoformat(shift['end'])
            if start in seen:raise ValueError('Turno duplicado')
            seen.add(start)
            try:
                plan=self.shift_plan(origin_out,destination_out,origin_back,destination_back,start,end,
                    access['home_to_out_stop'],access['out_stop_to_work'],buffer,window,
                    walk_work_return=access['work_to_back_stop'],walk_home_return=access['back_stop_to_home'])
                if max_minutes is not None:
                    for key in ('outbound','return'):plan[key]=[leg for leg in plan[key] if leg['door_to_door_minutes']<=max_minutes]
                compatible=bool(plan['outbound'] and plan['return'])
                result.append({'start':shift['start'],'end':shift['end'],'scheduled_round_trip_found':compatible,'plan':plan})
            except ValueError as exc:
                result.append({'start':shift['start'],'end':shift['end'],'scheduled_round_trip_found':False,'hold_reason':str(exc)})
        return {'status':'SCHEDULED_ALL_REQUESTED_SHIFTS' if all(r['scheduled_round_trip_found'] for r in result) else 'HOLD',
                'shifts':result,'checked_shift_count':len(result),'access_verified':False,'route_autoapproved':False,
                'unrequested_dates_verified':False,'car_assumed':False,'max_minutes':max_minutes,
                'limitation':'Solo fechas/turnos solicitados y horarios programados. Accesos a pie declarados, no comprobados; no acredita la ruta ni autoriza una candidatura.'}
