"""Verify the installed native backend's actual GPU model and inference type."""
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.localai'
sys.path.insert(0, str(ROOT))
from add_whisper import model_pin
PIN = model_pin('whisper-large-v3')
BACKEND = STATE / 'backends' / PIN['backend_name']
sys.path.insert(0, str(BACKEND))
import backend
import backend_pb2


def verify(model_id='whisper-large-v3'):
    PIN = model_pin(model_id)
    model = STATE / 'models' / PIN['directory']
    for filename, expected in PIN['files'].items():
        checksum = hashlib.sha256()
        with (model / filename).open('rb') as f:
            while chunk := f.read(8 * 1024 * 1024):
                checksum.update(chunk)
        assert checksum.hexdigest() == expected, filename
    service = backend.BackendServicer()
    reply = service.LoadModel(backend_pb2.ModelOptions(Model=str(model), CUDA=True), None)
    assert reply.success, reply.message
    assert service.model.model.device == 'cuda'
    assert service.model.model.compute_type == 'float32'
    report = {'model': PIN['model_id'], 'source_model': PIN['repo'], 'revision': PIN['revision'],
              'model_class': type(service.model).__name__, 'engine_class': type(service.model.model).__name__,
              'device': service.model.model.device, 'compute_type': service.model.model.compute_type,
              'files_verified': True, 'model_sha256': PIN['files']['model.bin'],
              'native_backend_load_passed': True,
              'packages': {p: importlib.metadata.version(p) for p in ('faster-whisper', 'ctranslate2', 'torch', 'numpy')}}
    # Exercise the real RPC method: language forwarding and text/segment conversion.
    captured = []
    class ProbeModel:
        def transcribe(self, audio, **kwargs):
            captured.append(kwargs['language'])
            segment = SimpleNamespace(start=0, end=1, text='测试 model 123', words=[])
            return iter([segment]), None
    service.model = ProbeModel()
    for sent, expected in (('', None), ('auto', None), ('en', 'en'), ('zh', 'zh'), ('zh-tw', 'zh')):
        result = service.AudioTranscription(backend_pb2.TranscriptRequest(
            dst=str(STATE / 'samples/chinese.wav'), language=sent), None)
        assert captured[-1] == expected, (sent, captured)
        assert result.text == '測試 model 123'
        assert ''.join(segment.text for segment in result.segments) == result.text
    report['language_forwarding_and_conversion_passed'] = True
    (STATE / 'reports' / (model_id + '-model.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    verify()
