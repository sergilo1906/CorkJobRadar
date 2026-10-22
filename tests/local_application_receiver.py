"""Owned loopback test receiver. Never an ATS endpoint or production transport.

Uses real TCP/HTTP and durable SQLite receipt metadata, synthetic data only.
No arbitrary URL parameter, email delivery, request-body logs or external bind.
"""
from contextlib import contextmanager
from email.parser import BytesParser
from email.policy import default
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import secrets
import sqlite3
from threading import Thread


@contextmanager
def application_receiver(path,job_id,expected_values,cv_hash,*,response_mode='receipt',cv_field='resume'):
    token=secrets.token_hex(24);prefix='/'+token
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE receipts(job_id TEXT PRIMARY KEY,reference TEXT,request_hash TEXT,cv_hash TEXT,field_hashes TEXT)')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # No URL, multipart bytes or candidate logs.
        def reply(self,status,body,kind='application/json'):
            self.send_response(status);self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'none'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if self.path!=prefix+'/form':self.reply(404,b'{}');return
            html='''<!doctype html><meta charset="utf-8"><h1>OWNED LOCAL TEST ONLY</h1>
<form method="POST" enctype="multipart/form-data" action="submit">
<label for="name">Full name</label><input id="name" name="name" required>
<label for="email">Email</label><input id="email" name="email" type="email" required>
<label for="phone">Phone</label><input id="phone" name="phone" type="tel" required>
<label for="linkedin">LinkedIn URL</label><input id="linkedin" name="linkedin" type="url" required>
<label for="availability">Availability</label><input id="availability" name="availability" required>
<label for="question">Which support task can you perform?</label><input id="question" name="question" required>
<label for="resume">Resume</label><input id="resume" name="resume" type="file" required>
<button type="submit">Submit owned test</button></form>'''
            self.reply(200,html.encode('utf-8'),'text/html; charset=utf-8')
        def do_POST(self):
            if self.path!=prefix+'/submit':self.reply(404,b'{}');return
            if self.headers.get('Origin')!=origin:self.reply(403,b'{}');return
            try:length=int(self.headers.get('Content-Length','0'))
            except ValueError:length=0
            if not 0<length<=2_000_000:self.reply(413,b'{}');return
            kind=self.headers.get('Content-Type','')
            if not kind.startswith('multipart/form-data;'):self.reply(415,b'{}');return
            body=self.rfile.read(length)
            message=BytesParser(policy=default).parsebytes(('Content-Type: '+kind+'\r\nMIME-Version: 1.0\r\n\r\n').encode('ascii')+body)
            fields={};files={}
            for part in message.iter_parts():
                key=part.get_param('name',header='content-disposition')
                if key in fields or key in files:self.reply(400,b'{}');return
                raw=part.get_payload(decode=True)
                if part.get_filename():files[key]=raw
                else:fields[key]=raw.decode('utf-8')
            if fields!=expected_values or set(files)!={cv_field} or hashlib.sha256(files[cv_field]).hexdigest()!=cv_hash:
                self.reply(422,b'{}');return
            reference='OWNED-TEST-'+secrets.token_hex(12);request_hash=hashlib.sha256(body).hexdigest()
            hashes={key:hashlib.sha256(value.encode('utf-8')).hexdigest() for key,value in fields.items()}
            try:
                with sqlite3.connect(path) as con:con.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',(job_id,reference,request_hash,cv_hash,json.dumps(hashes)))
            except sqlite3.IntegrityError:self.reply(409,b'{"duplicate":true}');return
            response={'received':True,'environment':'OWNED_LOCAL_TEST_ONLY','job_id':job_id,'reference':reference,'request_hash':request_hash,'cv_hash':cv_hash}
            self.reply(200,json.dumps(response if response_mode=='receipt' else {'message':'200 alone is not a receipt'}).encode('utf-8'))
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.daemon_threads=True
    origin='http://127.0.0.1:'+str(server.server_port)
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    try:yield {'origin':origin,'form_url':origin+prefix+'/form','submit_url':origin+prefix+'/submit','db':path}
    finally:server.shutdown();server.server_close();worker.join(timeout=5)
