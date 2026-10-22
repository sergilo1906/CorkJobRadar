"""Portable, bounded CPU inference; process lives only for the calling worker."""
import ctypes
import json
import os
import socket
import secrets
import subprocess
import time
import hashlib
from pathlib import Path
from contextvars import ContextVar
from contextlib import contextmanager
import httpx
from .config import ROOT

PORT=18081
ENDPOINT=f'http://127.0.0.1:{PORT}'
ACTIVE_MODEL=ContextVar('radar_local_model',default='qwen2.5-1.5b-instruct-q4_k_m.gguf')
SERVER_KEY=ContextVar('radar_server_key',default='')

def model_quality(model):
    path=ROOT/'data/model-quality.json'
    record=json.loads(path.read_text(encoding='utf-8')).get(model,{}) if path.exists() else {}
    if record.get('status')=='RECHAZADO':
        return 'RECHAZADO'
    from .semantic import PROMPT_VERSION,VALIDATION_VERSION
    return record.get('status','EN_EVALUACION') if record.get('prompt_version')==PROMPT_VERSION and record.get('validation_version')==VALIDATION_VERSION else 'EN_EVALUACION'

def is_validated_model():
    path=ROOT/'config/local_model.json'
    if not path.exists():
        return False
    config=json.loads(path.read_text(encoding='utf-8'))
    return model_quality(Path(config['model']).name)=='VALIDADO_MUESTRA_LIMITADA'

def model_headers():
    key=SERVER_KEY.get()
    return {'Authorization':'Bearer '+key} if key else {}


def verify_model_artifact(model,folder):
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    candidates=[entry for entry in manifest.get('model_files',[]) if entry.get('rfilename')==model.name]
    if len(candidates)!=1:raise RuntimeError('Manifest sin identidad única del modelo')
    entry=candidates[0];expected=entry.get('lfs',{}).get('sha256')
    if not expected or model.stat().st_size!=entry.get('size'):raise RuntimeError('Tamaño/huella del modelo no coincide con el manifest verificado')
    digest=hashlib.sha256()
    with model.open('rb') as stream:
        if stream.read(4)!=b'GGUF':raise RuntimeError('Formato de modelo no reconocido')
        stream.seek(0)
        for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
    if digest.hexdigest()!=expected:raise RuntimeError('SHA-256 del modelo no coincide con su procedencia; inferencia suspendida')
    return expected


def available_ram():
    if os.name!='nt':
        return None
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),
                  ('total',ctypes.c_ulonglong),('available',ctypes.c_ulonglong),
                  ('total_page',ctypes.c_ulonglong),('available_page',ctypes.c_ulonglong),
                  ('total_virtual',ctypes.c_ulonglong),('available_virtual',ctypes.c_ulonglong),
                  ('extended',ctypes.c_ulonglong)]
    status=Memory();status.length=ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError('No se pudo comprobar RAM disponible')
    return status.available


@contextmanager
def local_server(runtime_config=None,evaluation=False):
    folder=ROOT/'data/local-model'
    executable=folder/'runtime/llama-server.exe'
    model=folder/'qwen2.5-1.5b-instruct-q4_k_m.gguf'
    settings={}
    configuration=Path(runtime_config) if runtime_config else ROOT/'config/local_model.json'
    if configuration.exists():
        settings=json.loads(configuration.read_text(encoding='utf-8'))
        executable=(ROOT/settings['executable']).resolve();model=(ROOT/settings['model']).resolve()
        if not executable.is_relative_to(ROOT/'data') or not model.is_relative_to(ROOT/'data'):
            raise ValueError('Modelo/motor deben estar dentro de data del proyecto')
        folder=model.parent
    if not executable.exists() or not model.exists() or not (folder/'manifest.json').exists():
        raise RuntimeError('Modelo portátil no instalado/verificado; conserva análisis documental')
    if not evaluation and model_quality(model.name)!='VALIDADO_MUESTRA_LIMITADA':
        raise RuntimeError('El modelo local no ha superado validación semántica; análisis profundo pendiente')
    if not evaluation:
        verify_model_artifact(model,folder)
    free=available_ram()
    if free is not None and free < (1_500_000_000 if settings.get('gpu') else model.stat().st_size+800_000_000):
        raise RuntimeError('RAM libre insuficiente para inferencia local conservadora; conserva análisis documental')
    if settings.get('gpu'):
        check=subprocess.run(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
        if check.returncode or int(check.stdout.strip().splitlines()[0])*1024*1024 < model.stat().st_size+650_000_000:
            raise RuntimeError('VRAM libre insuficiente; no se inicia el modelo GPU')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',PORT))  # Never reuse or terminate an unrelated local service.
    env=os.environ.copy()
    for key in ('TEMP','TMP','HF_HOME','LLAMA_CACHE'):
        env[key]=str(ROOT/'data/tmp')
    log=(ROOT/'logs/local-model-server.log').open('a',encoding='utf-8')
    process=None
    token=None
    key_token=None
    try:
        key=secrets.token_urlsafe(32)
        arguments=[str(executable),'-m',str(model),'--host','127.0.0.1','--port',str(PORT),
            '-c','4096','-t','2','-tb','2','-np','1','-b','128','-ub','64','--no-webui','--offline',
            '--log-colors','off','--api-key',key]
        if settings.get('gpu'):
            arguments+=['-ngl',str(settings.get('gpu_layers',28)),'--device',settings.get('device','Vulkan1'),'--reasoning','off']
            if settings.get('diagnostic'):
                arguments+=['--log-verbosity','4']
        process=subprocess.Popen(arguments,cwd=ROOT,env=env,stdout=log,stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        deadline=time.monotonic()+min(180,settings.get('startup_timeout',50))
        ready=False
        with httpx.Client(timeout=2,trust_env=False,headers={'Authorization':'Bearer '+key}) as client:
            while time.monotonic()<deadline:
                if process.poll() is not None:
                    raise RuntimeError('El motor local no arrancó; consultar logs/local-model-server.log')
                try:
                    if client.get(ENDPOINT+'/health').status_code==200:
                        ready=True
                        break
                except httpx.TransportError:
                    pass
                time.sleep(.25)
        if not ready:
            raise RuntimeError('El motor local no estuvo disponible dentro del tiempo de arranque configurado')
        token=ACTIVE_MODEL.set(model.name)
        key_token=SERVER_KEY.set(key)
        yield {'pid':process.pid,'model':model.name,'threads':2,'context':4096,'ram_available_before':free,'gpu':bool(settings.get('gpu'))}
    finally:
        if token is not None:
            ACTIVE_MODEL.reset(token)
        if key_token is not None:
            SERVER_KEY.reset(key_token)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=5)
        log.close()
