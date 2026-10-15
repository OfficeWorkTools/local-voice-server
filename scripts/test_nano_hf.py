"""Check Nano language, audio, output bounds and publication isolation without weights."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import wave

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(LOCALAI_ASR_ROOT=str(ROOT), HF_HUB_OFFLINE='1', CUDA_VISIBLE_DEVICES='')
sys.path.insert(0, str(ROOT / '.localai/backends/cpu-nano-hf'))
import backend
import backend_pb2 as pb
import torch

for value, expected in [('', None), ('auto', None), ('zh-tw', 'zh'), ('EN-US', 'en'), ('ja', 'ja')]:
    assert backend.language_mode(value) == expected
try:
    backend.language_mode('invalid')
except ValueError:
    pass
else:
    raise AssertionError('Accepted unsupported language')
service = backend.BackendServicer()
assert not service.LoadModel(pb.ModelOptions(Model='unknown', CUDA=True), None).success
assert not service.LoadModel(pb.ModelOptions(Model='unknown'), None).success
captured = []
def prepare(**kwargs):
    captured.append(kwargs)
    return SimpleInputs(input_ids=torch.tensor([[1, 2]]))
class SimpleInputs(dict):
    __getattr__ = dict.__getitem__
service.processor = SimpleNamespace(apply_transcription_request=prepare, batch_decode=lambda *a, **k: ['测试'])
service.model = SimpleNamespace(generation_config=SimpleNamespace(eos_token_id=9),
                                generate=lambda **k: torch.tensor([[1, 2, 3, 9]]))
request = pb.TranscriptRequest(dst=str(ROOT / '.localai/samples/chinese.wav'), language='zh-tw')
result = service.AudioTranscription(request, None)
assert result.text == result.segments[0].text == '測試'
assert captured[0]['language'] == 'zh'
service.model.generate = lambda **k: torch.tensor([[1, 2, 3]])
try:
    service.AudioTranscription(request, None)
except RuntimeError as error:
    assert 'output limit' in str(error)
else:
    raise AssertionError('Accepted truncated output')
with tempfile.TemporaryDirectory() as directory:
    audio = Path(directory) / 'silent.wav'
    with wave.open(str(audio), 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\0' * 32000)
    assert service.AudioTranscription(pb.TranscriptRequest(dst=str(audio)), None).text == ''
    with wave.open(str(audio), 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\0' * (16000 * 61 * 2))
    try:
        backend.read_audio(audio)
    except ValueError:
        pass
    else:
        raise AssertionError('Accepted audio longer than 60 seconds')

sys.path.insert(0, str(ROOT))
import add_nano_hf as installer
with tempfile.TemporaryDirectory() as directory:
    installer.STATE = Path(directory)
    installer.BACKEND = installer.STATE / 'backend'
    installer.STAGING = installer.STATE / 'staging'
    installer.REPORT = installer.STATE / 'reports'
    installer.ensure_owner = lambda: None
    for folder in (installer.BACKEND, installer.STAGING, installer.REPORT, installer.STATE / 'models'):
        folder.mkdir(parents=True)
    code = installer.BACKEND / 'backend.py'; code.write_text('test code')
    config = installer.STAGING / (installer.PIN['model_id'] + '.yaml'); config.write_text('test config')
    proof = {'passed': True, 'model': installer.PIN['model_id'], 'config_sha256': installer.digest(config),
             'backend_sha256': installer.digest(code)}
    native = {'native_backend_load_passed': True, 'model': installer.PIN['model_id'],
              'engine_class': 'FunAsrNanoForConditionalGeneration', 'device': 'cpu',
              'parameter_dtypes': ['torch.float32'], 'files_sha256': installer.PIN['files'],
              'packages': installer.PIN['packages'], 'backend_sha256': installer.digest(code)}
    api_path = installer.REPORT / 'nano-hf-api-8768.json'
    model_path = installer.REPORT / 'nano-hf-model.json'
    api_path.write_text(json.dumps(proof)); model_path.write_text(json.dumps(native))
    installer.publish()
    assert (installer.STATE / 'models' / config.name).read_bytes() == config.read_bytes()
    for target, original, field, value in [(api_path, proof, 'model', 'wrong'),
            (api_path, proof, 'config_sha256', 'wrong'), (api_path, proof, 'backend_sha256', 'wrong'),
            (model_path, native, 'parameter_dtypes', ['torch.float16']), (model_path, native, 'files_sha256', {})]:
        target.write_text(json.dumps({**original, field: value}))
        try:
            installer.publish()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Accepted invalid evidence: ' + field)
        target.write_text(json.dumps(original))
print('PASS: Nano CPU guards, languages, s2t, output limit, silence, audio limit and publication evidence')
