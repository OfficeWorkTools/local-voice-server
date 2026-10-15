"""Verify the actual native Nano class, CPU FP32 parameters and fixed artifacts."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.localai'
PIN = json.loads((ROOT / 'config/versions.json').read_text())['nano_hf']


def verify():
    for name, expected in PIN['packages'].items():
        assert importlib.metadata.version(name) == expected, name
    for name, expected in PIN['files'].items():
        with (STATE / 'models' / PIN['directory'] / name).open('rb') as file:
            assert hashlib.file_digest(file, 'sha256').hexdigest() == expected, name
    folder = STATE / 'backends' / PIN['backend_name']
    os.environ.update(LOCALAI_ASR_ROOT=str(ROOT), CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1')
    sys.path.insert(0, str(folder))
    import backend
    import backend_pb2 as pb
    service = backend.BackendServicer()
    result = service.LoadModel(pb.ModelOptions(Model=PIN['directory'], CUDA=False), None)
    assert result.success, result.message
    assert service.evidence['engine_class'] == 'FunAsrNanoForConditionalGeneration'
    assert service.evidence['processor_class'] == 'FunAsrNanoProcessor'
    transcripts = []
    for filename in ('chinese.wav', 'english.wav', 'mixed.wav'):
        result = service.AudioTranscription(pb.TranscriptRequest(dst=str(STATE / 'samples' / filename),
                                           ModelIdentity=PIN['directory']), None)
        assert result.text.strip()
        assert ''.join(s.text for s in result.segments) == result.text
        transcripts.append({'sample': filename, 'text': result.text})
    report = {**service.evidence, 'revision': PIN['revision'], 'source_model': PIN['repo'],
              'native_backend_load_passed': True, 'files_sha256': PIN['files'], 'packages': PIN['packages'],
              'backend_sha256': hashlib.sha256((folder / 'backend.py').read_bytes()).hexdigest(),
              'transcripts': transcripts}
    (STATE / 'reports/nano-hf-model.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    verify()
