"""Straight-line radius. Private origins never leave DPAPI storage or memory."""
import json
import math
import re
from datetime import datetime,timedelta
from urllib.parse import urlsplit
from ..config import now,digest
from .vault import protect

DEFAULT_ORIGIN={'latitude':51.88944,'longitude':-8.44639,
                'source':'https://en.wikipedia.org/wiki/Ballinlough%2C_Cork',
                'approximate':True}


def point(latitude,longitude):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (latitude,longitude)):
        raise ValueError('FINITE_COORDINATES_REQUIRED')
    if not -90<=latitude<=90 or not -180<=longitude<=180:raise ValueError('COORDINATES_OUT_OF_RANGE')
    return float(latitude),float(longitude)


def distance_km(lat1,lon1,lat2,lon2):
    a,b=point(lat1,lon1);c,d=point(lat2,lon2)
    p,q=math.radians(a),math.radians(c)
    h=math.sin((q-p)/2)**2+math.cos(p)*math.cos(q)*math.sin(math.radians(d-b)/2)**2
    return 6371.0088*2*math.asin(math.sqrt(min(1,max(0,h))))


def origin(db):
    rows=db.rows('SELECT * FROM it_selection_origins ORDER BY id DESC LIMIT 1')
    if not rows:return {**DEFAULT_ORIGIN,'binding_hash':digest(DEFAULT_ORIGIN)}
    row=rows[0]
    if digest(bytes(row['encrypted_value']).hex())!=row['ciphertext_hash']:raise ValueError('ORIGIN_INTEGRITY_FAILURE')
    return {**json.loads(protect(row['encrypted_value'],decrypt=True)),'binding_hash':row['ciphertext_hash']}


def save_origin(db,latitude,longitude,*,confirmed=False):
    if not confirmed:raise PermissionError('EXPLICIT_LOCAL_ORIGIN_REQUIRED')
    lat,lon=point(latitude,longitude)
    encrypted=protect(json.dumps({'latitude':lat,'longitude':lon,'approximate':False}).encode())
    return db.execute('INSERT INTO it_selection_origins(created_at,encrypted_value,ciphertext_hash) VALUES(?,?,?)',
                      (now(),encrypted,digest(encrypted.hex())))


def save_worksite(db,job_id,latitude,longitude,evidence_url,content_hash,*,confirmed=False,valid_days=30):
    if not confirmed:raise PermissionError('EXPLICIT_WORKSITE_VERIFICATION_REQUIRED')
    lat,lon=point(latitude,longitude);u=urlsplit(evidence_url)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('PUBLIC_WORKSITE_EVIDENCE_URL_REQUIRED')
    if type(valid_days)!=int or not 1<=valid_days<=90:raise ValueError('WORKSITE_EXPIRY_REQUIRED')
    with db.transaction() as con:
        con.execute('BEGIN IMMEDIATE')
        if db.rows('SELECT content_hash FROM jobs WHERE id=?',(job_id,))[0]['content_hash']!=content_hash:raise ValueError('JOB_CHANGED_RECHECK_WORKSITE')
        return db.execute('INSERT INTO it_worksite_evidence(job_id,content_hash,latitude,longitude,evidence_url,verified_at,expires_at) VALUES(?,?,?,?,?,?,?)',
            (job_id,content_hash,lat,lon,evidence_url,now(),(datetime.fromisoformat(now())+timedelta(days=valid_days)).isoformat()))


def location_assessment(db,job,origin_point=None):
    o=origin_point or origin(db)
    if job.get('mode')=='REMOTE':
        return {'state':'REMOTE_SEPARATE','distance_km':None,'worksite_verified':False,'origin_hash':o['binding_hash'],
                'reason':'Remoto separado; requiere autorización adicional y comprobar trabajo desde Irlanda.'}
    rows=db.rows('SELECT * FROM it_worksite_evidence WHERE job_id=? AND content_hash=? ORDER BY id DESC LIMIT 1',(job['id'],job['content_hash']))
    site=None;source=None;verified=False
    if rows and datetime.fromisoformat(rows[0]['expires_at'])>datetime.fromisoformat(now()):
        site=(rows[0]['latitude'],rows[0]['longitude']);source=rows[0]['evidence_url'];verified=True
    else:
        raw=json.loads(job['raw']) if isinstance(job.get('raw'),str) else job.get('raw',{})
        structured=raw.get('location',{})
        # Country is taken from the advertised job location, never employer headquarters.
        country=structured.get('country','') if isinstance(structured,dict) else ''
        if isinstance(country,dict):country=country.get('name','')
        if isinstance(country,str) and country and country.casefold() not in {'ie','irl','ireland','republic of ireland'}:
            if re.fullmatch('[a-zA-Z]{2}',country) or country.casefold() in {'united states','united kingdom','canada','india','australia','germany','poland','france','spain','mexico'}:
                return {'state':'OUTSIDE_RADIUS','distance_km':None,'worksite_verified':False,'origin_hash':o['binding_hash'],
                        'evidence_url':job['url'],'reason':'País de trabajo publicado fuera de Irlanda y del círculo de Cork; no se inventa distancia al centro.'}
        places=raw.get('jobLocation',[]);places=places if isinstance(places,list) else [places]
        points=[]
        for place in places:
            if not isinstance(place,dict):continue
            geo=place.get('geo',{});address=place.get('address',{})
            if not isinstance(geo,dict):continue
            try:p=point(float(geo['latitude']),float(geo['longitude']))
            except (ValueError,TypeError,KeyError):continue
            points.append((p,isinstance(address,dict) and bool(address.get('streetAddress'))))
        if len(points)==1:site,verified=points[0];source=job['url']
        elif not points and isinstance(structured,dict):
            try:site=point(float(structured['latitude']),float(structured['longitude']));source=job['url']
            except (ValueError,TypeError,KeyError):pass
    if site is None:return {'state':'LOCATION_PENDING','distance_km':None,'worksite_verified':False,'origin_hash':o['binding_hash'],
                             'reason':'Centro de trabajo pendiente. La sede social y Cork/County Cork no son coordenadas verificadas del puesto.'}
    distance=distance_km(o['latitude'],o['longitude'],*site)
    state=('WITHIN_RADIUS' if distance<=50+1e-9 else 'OUTSIDE_RADIUS') if verified else 'LOCATION_PENDING'
    return {'state':state,'distance_km':distance,'worksite_verified':bool(verified),'origin_hash':o['binding_hash'],
            'evidence_url':source,'reason':'Distancia geodésica al centro publicado/verificado; no es duración de viaje.' if verified else 'Punto publicado sin precisión de centro de trabajo: no acredita inclusión ni exclusión.'}
