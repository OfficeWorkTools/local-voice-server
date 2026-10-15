"""Check CPU guards, language and nanosecond conversion, and per-model publication."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(LOCALAI_ASR_ROOT=str(ROOT), CUDA_VISIBLE_DEVICES='')
sys.path.insert(0, str(ROOT / '.localai/backends/cpu-breeze'))
import backend
import backend_pb2 as pb

for value, expected in [('auto', None), ('', None), ('zh-tw', 'zh'), ('EN-US', 'en')]:
    assert backend.language_mode(value) == expected
service = backend.BackendServicer()
assert not service.LoadModel(pb.ModelOptions(Model='unknown', CUDA=True), None).success
assert not service.LoadModel(pb.ModelOptions(Model='unknown'), None).success
captured = []
def transcribe(audio, **kwargs):
    captured.append(kwargs)
    word = SimpleNamespace(start=0.25, end=1.25, word='测试')
    return [SimpleNamespace(id=0, start=0.25, end=1.25, text='测试', words=[word])], None
service.model = SimpleNamespace(transcribe=transcribe)
result = service.AudioTranscription(pb.TranscriptRequest(dst=str(ROOT / '.localai/samples/chinese.wav'),
                                   language='zh-tw', timestamp_granularities=['word']), None)
assert captured[0]['language'] == 'zh' and captured[0]['word_timestamps']
assert result.text == result.segments[0].text == result.segments[0].words[0].text == '測試'
assert result.segments[0].start == 250000000 and result.segments[0].words[0].end == 1250000000
sys.path.insert(0, str(ROOT))
import add_breeze as installer
with tempfile.TemporaryDirectory() as directory:
    installer.STATE = Path(directory)
    installer.BACKEND = installer.STATE / 'backend'
    installer.STAGING = installer.STATE / 'staging'
    installer.REPORT = installer.STATE / 'reports'
    installer.ensure_owner = lambda: None
    for folder in (installer.BACKEND, installer.STAGING, installer.REPORT, installer.STATE / 'models'):
        folder.mkdir(parents=True)
    code = installer.BACKEND / 'backend.py'; code.write_text('test backend')
    for model_id, profile in installer.PIN['profiles'].items():
        config = installer.STAGING / (model_id + '.yaml'); config.write_text(model_id)
        proof = {'passed': True, 'model': model_id, 'config_sha256': installer.digest(config), 'backend_sha256': installer.digest(code)}
        native = {'native_backend_load_passed': True, 'model': model_id, 'device': 'cpu', 'compute_type': 'int8_float32',
                  'source_files_sha256': profile['files'], 'converted_files_sha256': profile['converted_files'],
                  'packages': installer.PIN['packages'], 'backend_sha256': installer.digest(code)}
        (installer.REPORT / (profile['report_prefix'] + '-api-8768.json')).write_text(json.dumps(proof))
        (installer.REPORT / (profile['report_prefix'] + '-model.json')).write_text(json.dumps(native))
    installer.publish()
    target = installer.STATE / 'models' / config.name
    assert target.read_bytes() == config.read_bytes()
    path = installer.REPORT / (profile['report_prefix'] + '-api-8768.json')
    for field, value in [('model', 'wrong-model'), ('config_sha256', 'wrong'), ('backend_sha256', 'wrong')]:
        path.write_text(json.dumps({**proof, field: value}))
        try:
            installer.publish()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Accepted bad Breeze evidence: ' + field)
    path.write_text(json.dumps(proof))
    (installer.REPORT / (profile['report_prefix'] + '-model.json')).write_text(json.dumps({**native, 'converted_files_sha256': {}}))
    try:
        installer.publish()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Accepted incorrect converted weight evidence')
print('PASS: Breeze CPU/language/s2t/time units and separate publication evidence')
