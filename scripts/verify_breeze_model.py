"""Verify official source and converted hashes, actual CPU INT8 load and ASR."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.localai'
PIN = json.loads((ROOT / 'config/versions.json').read_text())['breeze_cpu']


def verify(model_id):
    profile = PIN['profiles'][model_id]
    for name, version in PIN['packages'].items():
        assert importlib.metadata.version(name) == version, name
    for directory, files in [(profile['source_directory'], profile['files']), (profile['directory'], profile['converted_files'])]:
        for name, sha in files.items():
            with (STATE / 'models' / directory / name).open('rb') as file:
                assert hashlib.file_digest(file, 'sha256').hexdigest() == sha, name
    folder = STATE / 'backends' / PIN['backend_name']
    os.environ.update(LOCALAI_ASR_ROOT=str(ROOT), CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1')
    sys.path.insert(0, str(folder))
    import backend
    import backend_pb2 as pb
    service = backend.BackendServicer()
    result = service.LoadModel(pb.ModelOptions(Model=profile['directory'], CUDA=False), None)
    assert result.success, result.message
    assert service.evidence['engine_class'] == 'Whisper'
    transcripts = []
    samples = ('chinese.wav', 'english.wav', 'mixed.wav') if model_id == 'breeze-asr-25-cpu' else ('taigi.wav',)
    for filename in samples:
        result = service.AudioTranscription(pb.TranscriptRequest(dst=str(STATE / 'samples' / filename),
                                           language='zh', ModelIdentity=profile['directory']), None)
        assert result.text.strip()
        assert ''.join(s.text for s in result.segments) == result.text
        transcripts.append({'sample': filename, 'text': result.text})
    report = {**service.evidence, 'revision': profile['revision'], 'native_backend_load_passed': True,
              'source_files_sha256': profile['files'], 'converted_files_sha256': profile['converted_files'],
              'packages': PIN['packages'], 'backend_sha256': hashlib.sha256((folder / 'backend.py').read_bytes()).hexdigest(),
              'transcripts': transcripts}
    (STATE / 'reports' / (profile['report_prefix'] + '-model.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    verify(sys.argv[1])
