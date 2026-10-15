"""Verify real CPU LoadModel, immutable files and native transcription."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.localai'
PINS = json.loads((ROOT / 'config/versions.json').read_text())['modern_cpu_asr']


def verify(model_id):
    profile = PINS['profiles'][model_id]
    folder = STATE / 'backends' / PINS['backend_name']
    os.environ['LOCALAI_ASR_ROOT'] = str(ROOT)
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    sys.path.insert(0, str(folder))
    import backend
    import backend_pb2 as pb
    for package, expected in PINS['base_packages'].items():
        assert importlib.metadata.version(package) == expected, (package, importlib.metadata.version(package), expected)
    for name, expected in profile['files'].items():
        path = STATE / 'models' / profile['directory']
        if profile['engine'] != 'audio-cpp':
            path = path / name
        with path.open('rb') as f:
            assert hashlib.file_digest(f, 'sha256').hexdigest() == expected, name
    service = backend.BackendServicer()
    onnx_evidence = {}
    if profile['engine'] == 'sherpa-onnx':
        sys.path.insert(0, str(folder / 'vendor'))
        import onnx
        from collections import Counter
        graph = onnx.load(str(STATE / 'models' / profile['directory'] / 'model.onnx'), load_external_data=False)
        types = Counter(onnx.TensorProto.DataType.Name(t.data_type) for t in graph.graph.initializer)
        quant = sorted({n.op_type for n in graph.graph.node if 'quantize' in n.op_type.lower()})
        assert types == {'FLOAT': 917} and not quant, (types, quant)
        onnx_evidence = {'initializer_types': dict(types), 'quantization_operators': quant}
        del graph
    try:
        result = service.LoadModel(pb.ModelOptions(Model=profile['directory'], CUDA=False), None)
        assert result.success, result.message
        transcripts = []
        for filename in ('chinese.wav', 'english.wav', 'mixed.wav'):
            result = service.AudioTranscription(pb.TranscriptRequest(dst=str(STATE / 'samples' / filename), ModelIdentity=profile['directory']), None)
            assert result.text.strip(), (filename, result)
            if result.segments:
                assert ''.join(s.text for s in result.segments) == result.text
            transcripts.append({'sample': filename, 'text': result.text})
        if service.child:
            maps = Path(f'/proc/{service.child.pid}/maps').read_text()
            assert not any(name in maps for name in ('libcuda.', 'libcublas', 'libcudnn'))
        report = {**service.evidence, **onnx_evidence, 'source_model': profile['repo'], 'revision': profile['revision'],
                  'files_verified': True, 'files_sha256': profile['files'], 'native_backend_load_passed': True,
                  'backend_sha256': hashlib.sha256((folder / 'backend.py').read_bytes()).hexdigest(),
                  'transcripts': transcripts, 'base_packages': PINS['base_packages']}
        (STATE / 'reports' / (model_id + '-model.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    finally:
        service.close()


if __name__ == '__main__':
    verify(sys.argv[1])
