import hashlib
import json
import pytest
from corkjobradar.local_model import verify_model_artifact


def test_model_artifact_integrity_rejects_same_size_tampering(tmp_path):
    model=tmp_path/'fixture.gguf';content=b'GGUFsynthetic-test-only'
    model.write_bytes(content)
    manifest={'model_files':[{'rfilename':model.name,'size':len(content),'lfs':{'sha256':hashlib.sha256(content).hexdigest()}}]}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    assert verify_model_artifact(model,tmp_path)==hashlib.sha256(content).hexdigest()
    model.write_bytes(content[:-1]+b'X')
    with pytest.raises(RuntimeError,match='SHA-256'):verify_model_artifact(model,tmp_path)


def test_model_artifact_requires_unique_manifest_identity_and_gguf(tmp_path):
    model=tmp_path/'fixture.gguf';content=b'FAKE-TEST'
    model.write_bytes(content)
    entry={'rfilename':model.name,'size':len(content),'lfs':{'sha256':hashlib.sha256(content).hexdigest()}}
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'model_files':[entry,entry]}),encoding='utf-8')
    with pytest.raises(RuntimeError,match='única'):verify_model_artifact(model,tmp_path)
    manifest.write_text(json.dumps({'model_files':[entry]}),encoding='utf-8')
    with pytest.raises(RuntimeError,match='Formato'):verify_model_artifact(model,tmp_path)
