"""Check CPU guards, language contracts and text/word conversion without models."""
import os
import json
import tempfile
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ['LOCALAI_ASR_ROOT'] = str(ROOT)
sys.path.insert(0, str(ROOT / '.localai/backends/cpu-modern-asr'))
import backend
import backend_pb2 as pb

qwen = backend.PIN['profiles']['qwen3-asr-0.6b-cpu']
fire = backend.PIN['profiles']['fireredasr2-aed-cpu']
for value, expected in [('', 'auto'), ('auto', 'auto'), ('zh-tw', 'zh'), ('EN-US', 'en')]:
    assert backend.language_mode(value, qwen) == expected
for value in ('zh', 'en', 'invalid'):
    try:
        backend.language_mode(value, fire)
    except ValueError:
        pass
    else:
        raise AssertionError('Accepted unsupported forced FireRed language')
service = backend.BackendServicer()
assert not service.LoadModel(pb.ModelOptions(Model='unknown', CUDA=True), None).success
assert not service.LoadModel(pb.ModelOptions(Model='unknown'), None).success
captured = []


def transcribe(request, **kwargs):
    captured.append(request.language)
    segment = pb.TranscriptSegment(text='测试')
    segment.words.add(text='测试')
    return pb.TranscriptResult(text='测试', segments=[segment])


service.profile = qwen
service.stub = SimpleNamespace(AudioTranscription=transcribe)
service.headers = []
result = service.AudioTranscription(pb.TranscriptRequest(dst=str(ROOT / '.localai/samples/chinese.wav'), language='zh-tw'), None)
assert captured == ['Chinese']
assert result.text == result.segments[0].text == result.segments[0].words[0].text == '測試'
service.close()
print('PASS: CPU-only guards, FireRed Auto-only contract and s2t transcript/segment/word consistency')

sys.path.insert(0, str(ROOT))
import add_cpu_asr as installer

with tempfile.TemporaryDirectory() as directory:
    installer.STATE = Path(directory)
    installer.STAGING = installer.STATE / 'staging'
    installer.BACKEND = installer.STATE / 'backend'
    installer.ensure_owner = lambda: None
    for path in (installer.STAGING, installer.BACKEND, installer.STATE / 'reports', installer.STATE / 'models'):
        path.mkdir(parents=True)
    code = installer.BACKEND / 'backend.py'
    code.write_text('test backend')
    for model_id, profile in installer.PIN['profiles'].items():
        config = installer.STAGING / (model_id + '.yaml')
        config.write_text('name: ' + model_id)
        proof = {'passed': True, 'model': model_id, 'backend_sha256': installer.digest(code),
                 'config_sha256': installer.digest(config)}
        native = {'model': model_id, 'native_backend_load_passed': True, 'device': 'cpu',
                  'files_verified': True, 'files_sha256': profile['files'], 'backend_sha256': installer.digest(code)}
        reports = installer.STATE / 'reports'
        (reports / (model_id + '-api-8768.json')).write_text(json.dumps(proof))
        (reports / (model_id + '-model.json')).write_text(json.dumps(native))
    installer.publish()
    for model_id in installer.PIN['profiles']:
        assert (installer.STATE / 'models' / (model_id + '.yaml')).read_bytes() == (installer.STAGING / (model_id + '.yaml')).read_bytes()
    evidence = reports / (model_id + '-api-8768.json')
    for field, value in [('model', 'wrong'), ('backend_sha256', 'wrong'), ('config_sha256', 'wrong'), ('passed', False)]:
        evidence.write_text(json.dumps({**proof, field: value}))
        try:
            installer.publish()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Accepted invalid CPU API evidence: ' + field)
    evidence.write_text(json.dumps(proof))
    (reports / (model_id + '-model.json')).write_text(json.dumps({**native, 'files_sha256': {}}))
    try:
        installer.publish()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Accepted wrong native model hashes')
print('PASS: CPU publication rejects mismatched model, config, backend and weight evidence')
