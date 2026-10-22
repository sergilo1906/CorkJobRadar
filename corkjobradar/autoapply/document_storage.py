"""Content-addressed DPAPI assets. Parser values never escape in error messages."""
import hashlib
import json
import re
from pathlib import Path
from .vault import private_folder, protect


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def save_asset(db, content, kind):
    if not re.fullmatch(r'[a-z0-9-]{1,40}', kind): raise ValueError('DOCUMENT_ASSET_KIND_INVALID')
    sha = hashlib.sha256(content).hexdigest()
    path = private_folder(db) / (sha + '.' + kind + '.dpapi')
    if not path.exists():
        # Exclusive creation prevents competing writers truncating an existing asset.
        try:
            with path.open('xb') as stream:
                stream.write(protect(content))
        except FileExistsError:
            pass
    if protect(path.read_bytes(), True) != content:
        raise ValueError('DOCUMENT_ASSET_INTEGRITY_FAILED')
    return str(path), sha


def read_asset(db, row):
    try:
        path = Path(row['encrypted_path']).resolve()
        if not path.is_relative_to(private_folder(db)) or path.suffix != '.dpapi':
            raise ValueError()
        raw = protect(path.read_bytes(), True)
        if hashlib.sha256(raw).hexdigest() != row['file_hash']:
            raise ValueError()
        return raw
    except Exception:
        raise ValueError('DOCUMENT_ASSET_INTEGRITY_FAILED') from None
