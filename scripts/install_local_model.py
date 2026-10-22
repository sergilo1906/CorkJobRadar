"""Optional portable runtime/model. Every byte stays in this project.

Uses the inspected official release/model manifest, exact sizes and SHA-256.
No system installation, Python wheel cache, HF cache, or external inference.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import zipfile
import httpx

ROOT=Path(__file__).resolve().parents[1]


def download(client,url,path,size,sha):
    if path.exists() and path.stat().st_size==size and hashlib.file_digest(path.open('rb'),'sha256').hexdigest()==sha:
        print(path.name,'already verified',flush=True)
        return
    partial=path.with_suffix(path.suffix+'.part')
    checksum=hashlib.sha256();n=0
    with client.stream('GET',url) as response:
        response.raise_for_status()
        with partial.open('wb') as output:
            for block in response.iter_bytes(1024*1024):
                n+=len(block)
                if n>size:
                    raise ValueError('Download exceeds official manifest size')
                checksum.update(block);output.write(block)
    if n!=size or checksum.hexdigest()!=sha:
        raise ValueError('Download size/SHA-256 mismatch; runtime/model not activated')
    partial.replace(path)
    print(path.name,n,'SHA-256 verified',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',default='data/model-download-manifest.json')
    parser.add_argument('--destination',default='data/local-model')
    args=parser.parse_args()
    manifest=json.loads((ROOT/args.manifest).read_text(encoding='utf-8'))
    runtime=manifest['runtime'][0];model=manifest['model_files'][0]
    folder=(ROOT/args.destination).resolve()
    if not folder.is_relative_to((ROOT/'data').resolve()):
        raise ValueError('Portable files must stay in the project data folder')
    folder.mkdir(exist_ok=True)
    needed=runtime['size']+model['size']+500_000_000
    if shutil.disk_usage(ROOT).free<needed:
        raise RuntimeError('Insufficient project disk space')
    with httpx.Client(timeout=60,follow_redirects=True,trust_env=False) as client:
        archive=folder/runtime['name']
        if not runtime.get('digest','').startswith('sha256:'):
            raise ValueError('Official runtime digest unavailable; manual review required')
        download(client,runtime['browser_download_url'],archive,runtime['size'],runtime['digest'][7:])
        destination=folder/'runtime';destination.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                target=(destination/item.filename).resolve()
                if not target.is_relative_to(destination.resolve()) or item.file_size>100_000_000:
                    raise ValueError('Unexpected archive entry')
            bundle.extractall(destination)
        filename=model['rfilename'];revision=manifest['model_revision']
        repo=manifest.get('model_repo','Qwen/Qwen2.5-1.5B-Instruct-GGUF')
        url=f'https://huggingface.co/{repo}/resolve/{revision}/{filename}'
        download(client,url,folder/filename,model['size'],model['lfs']['sha256'])
        for name,url in [('LICENSE-llama.txt','https://raw.githubusercontent.com/ggml-org/llama.cpp/'+manifest['release']+'/LICENSE'),
                         ('LICENSE-Qwen.txt',f'https://huggingface.co/{repo}/raw/{revision}/LICENSE')]:
            r=client.get(url)
            if r.status_code==200:
                (folder/name).write_bytes(r.content)
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Portable files ready; no model process started',flush=True)


if __name__=='__main__':
    main()
