"""Owned simulated challenge and durable receiver. Never a CAPTCHA service."""
from contextlib import contextmanager
from email.parser import BytesParser
from email.policy import default
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import secrets
import sqlite3
from threading import Thread


@contextmanager
def human_receiver(path,job_id,expected,cv_hash,*,receipt=True,verification='captcha',redirect=False):
    sessions={};stats={'posts':0,'verifications':0,'forms':0}
    with sqlite3.connect(path) as con:con.execute('CREATE TABLE receipts(job_id TEXT PRIMARY KEY,request_hash TEXT,cv_hash TEXT)')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,body,kind='application/json',cookie=None):
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store')
            if cookie:self.send_header('Set-Cookie','owned_session='+cookie+'; HttpOnly; SameSite=Strict; Path=/')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def current(self):
            try:
                cookie=SimpleCookie(self.headers.get('Cookie',''));key=cookie['owned_session'].value
                return sessions.get(key)
            except (KeyError,ValueError):return None
        def do_GET(self):
            if self.path=='/session-status':
                status=self.current() or {'active':False,'human_verified':False}
                self.reply(200 if status['active'] else 410,json.dumps(status).encode());return
            if self.path!='/form':self.reply(404,b'{}');return
            if redirect:
                self.send_response(302);self.send_header('Location','https://redirect-target.invalid/form');self.end_headers();return
            token=secrets.token_hex(20);sessions[token]={'active':True,'human_verified':False};stats['forms']+=1
            challenge='<div class="g-recaptcha" data-human-verification>OWNED SIMULATED CHALLENGE</div>' if verification=='captcha' else '<div data-mfa-required>OWNED SIMULATED AUTHENTICATION</div>'
            html='''<!doctype html><meta charset="utf-8"><h1>OWNED HUMAN TEST ONLY</h1>
<form method="post" enctype="multipart/form-data" action="/submit">
<label for="name">Full name</label><input id="name" name="name" required>
<label for="email">Email</label><input id="email" name="email" required>
<label for="resume">Resume/CV</label><input id="resume" name="resume" type="file" required>
<label for="linkedin">LinkedIn Profile</label><input id="linkedin" name="linkedin" required>
<button type="submit">Submit owned test</button></form>
<section id="human" hidden>CHALLENGE<button id="verify" type="button">I complete the simulated verification</button></section>
<script>
let verified=false;
document.getElementById('resume').addEventListener('change',()=>{if(!verified)document.getElementById('human').hidden=false;});
document.getElementById('verify').addEventListener('click',async()=>{
const r=await fetch('/human-verify',{method:'POST'});
if(r.ok){verified=true;document.getElementById('human').hidden=true;}});
</script>'''.replace('CHALLENGE',challenge)
            self.reply(200,html.encode(),'text/html; charset=utf-8',token)
        def do_POST(self):
            status=self.current()
            if self.headers.get('Origin')!=origin or not status or not status['active']:
                self.reply(403,b'{}');return
            if self.path=='/human-verify':
                status['human_verified']=True;stats['verifications']+=1;self.reply(200,b'{"verified":true}');return
            if self.path!='/submit':self.reply(404,b'{}');return
            stats['posts']+=1
            if not status['human_verified']:self.reply(403,b'{}');return
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<2_000_000:self.reply(413,b'{}');return
            body=self.rfile.read(length);kind=self.headers.get('Content-Type','')
            message=BytesParser(policy=default).parsebytes(('Content-Type: '+kind+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
            fields={};files={}
            for part in message.iter_parts():
                key=part.get_param('name',header='content-disposition');value=part.get_payload(decode=True)
                if key in fields or key in files:self.reply(400,b'{}');return
                if part.get_filename():files[key]=value
                else:fields[key]=value.decode()
            if fields!=expected or set(files)!={'resume'} or hashlib.sha256(files['resume']).hexdigest()!=cv_hash:
                self.reply(422,b'{}');return
            request_hash=hashlib.sha256(body).hexdigest()
            try:
                with sqlite3.connect(path) as con:con.execute('INSERT INTO receipts VALUES(?,?,?)',(job_id,request_hash,cv_hash))
            except sqlite3.IntegrityError:self.reply(409,b'{}');return
            result={'received':True,'environment':'OWNED_HUMAN_TEST_ONLY','job_id':job_id,'reference':'OWNED-HUMAN-'+secrets.token_hex(8),'request_hash':request_hash,'cv_hash':cv_hash}
            self.reply(200,json.dumps(result if receipt else {'success':True}).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
    origin='http://127.0.0.1:'+str(server.server_port)
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    def expire():
        for status in sessions.values():status['active']=False
    try:yield {'url':origin+'/form','db':path,'stats':stats,'expire':expire}
    finally:server.shutdown();server.server_close();worker.join(timeout=5)
