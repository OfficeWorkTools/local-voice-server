#!/usr/bin/env python3
"""Prepare the pinned native GPU Whisper backend, then publish its tested profile."""
import argparse
import json
import shutil
import zipfile
from pathlib import Path
from deploy import ROOT, STATE, PINS, digest, download, run, ensure_owner

WHISPER_MODELS = {'whisper-large-v3': 'whisper', 'whisper-large-v3-turbo': 'whisper_turbo'}


def model_pin(model_id):
    return {**PINS['whisper'], **PINS[WHISPER_MODELS[model_id]]}


PIN = model_pin('whisper-large-v3')
BACKEND = STATE / 'backends' / PIN['backend_name']
STAGING = STATE / 'whisper-staging/models'


def patch_backend(original):
    anchors = {
        'import torch\n': 'import torch\nimport wave\nimport numpy as np\nfrom transcription_conversion import convert_text\n',
        'self.model = WhisperModel(request.Model, device=device, compute_type="default")':
            'if device != "cuda":\n                raise RuntimeError("This profile requires an NVIDIA CUDA GPU")\n'
            '            self.model = WhisperModel(request.Model, device=device, compute_type="float32", cpu_threads=8)\n'
            '            if self.model.model.device != "cuda" or self.model.model.compute_type != "float32":\n'
            '                raise RuntimeError("Whisper did not load as CUDA float32")\n'
            '            print("WHISPER_PROFILE device=cuda compute_type=float32", file=sys.stderr)',
        'segments, info = self.model.transcribe(request.dst, beam_size=5, condition_on_previous_text=False, word_timestamps=word_timestamps)':
            'language = request.language.strip().lower() or None\n'
            '            if language == "auto":\n                language = None\n'
            '            if language in ("zh-tw", "zh-cn"):\n                language = "zh"\n'
            '            with wave.open(request.dst, "rb") as wav:\n'
            '                if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):\n'
            '                    raise ValueError("Expected 16 kHz mono PCM16 WAV")\n'
            '                audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768.0\n'
            '            segments, info = self.model.transcribe(audio, language=language, task="transcribe", '
            'beam_size=5, temperature=0, condition_on_previous_text=False, word_timestamps=word_timestamps)',
        'text=word.word': 'text=convert_text(word.word)',
        'text=segment.text': 'text=convert_text(segment.text)',
        'text += segment.text': 'text += convert_text(segment.text)',
    }
    for old, new in anchors.items():
        if original.count(old) != 1:
            raise RuntimeError(f'Whisper patch anchor changed: {old}')
        original = original.replace(old, new)
    compile(original, 'patched-whisper-backend.py', 'exec')
    return original


def prepare():
    ensure_owner()
    if not (STATE / 'install.json').exists():
        raise RuntimeError('Install the existing LocalAI service with deploy.py first')
    binary = STATE / 'bin/local-ai'
    if digest(binary) != PINS['localai']['sha256']:
        raise RuntimeError('LocalAI binary checksum mismatch')
    metadata = BACKEND / 'metadata.json'
    if not metadata.exists():
        run(binary, 'backends', 'install', PIN['backend_uri'], PIN['backend_name'], PIN['backend_alias'],
            '--backend-galleries=[]', '--backends-path', STATE / 'backends', cwd=STATE)
    if json.loads(metadata.read_text())['digest'] != PIN['backend_digest']:
        raise RuntimeError('Whisper backend digest mismatch')
    source = BACKEND / 'backend.py'
    backup = BACKEND / 'backend.upstream.py'
    if not backup.exists():
        if digest(source) != PIN['backend_py_sha256']:
            raise RuntimeError('Unknown Whisper backend source; refusing to patch')
        shutil.copyfile(source, backup)
    if digest(backup) != PIN['backend_py_sha256']:
        raise RuntimeError('Whisper upstream backup checksum mismatch')
    original = backup.read_text()
    patched = patch_backend(original)
    if source.read_text() not in (original, patched):
        raise RuntimeError('Unrecognized Whisper backend edits; refusing to overwrite')
    model = STATE / 'models' / PIN['directory']
    for filename, checksum in PIN['files'].items():
        download(f"https://huggingface.co/{PIN['repo']}/resolve/{PIN['revision']}/{filename}", model / filename, checksum)
    english = PIN['english_sample']
    sample = STATE / 'samples/english-source.flac'
    download(english['url'], sample, english['sha256'])
    run('ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', sample, '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', STATE / 'samples/english.wav')
    link = BACKEND / PIN['directory']
    if link.is_symlink():
        if link.resolve() != model.resolve():
            raise RuntimeError('Whisper model symlink points elsewhere')
    elif link.exists():
        raise RuntimeError('Refusing to replace a real Whisper model directory')
    else:
        link.symlink_to('../../models/' + PIN['directory'], target_is_directory=True)
    wheel = STATE / 'conversion/opencc.whl'
    download(PINS['opencc']['url'], wheel, PINS['opencc']['sha256'])
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.startswith('opencc/'):
                if '..' in Path(name).parts:
                    raise RuntimeError('Unsafe OpenCC wheel path')
                archive.extract(name, STATE / 'conversion')
    link = BACKEND / 'opencc'
    if link.is_symlink():
        if link.resolve() != (STATE / 'conversion/opencc').resolve():
            raise RuntimeError('OpenCC symlink points elsewhere')
    elif link.exists():
        raise RuntimeError('Refusing to replace an existing OpenCC directory')
    else:
        link.symlink_to('../../conversion/opencc', target_is_directory=True)
    shutil.copyfile(ROOT / 'scripts/transcription_conversion.py', BACKEND / 'transcription_conversion.py')
    source.write_text(patched)
    STAGING.mkdir(parents=True, exist_ok=True)
    configuration = PIN['model_id'] + '.yaml'
    shutil.copyfile(ROOT / 'config' / configuration, STAGING / configuration)
    link = STAGING / PIN['directory']
    if not link.exists():
        link.symlink_to(model.resolve(), target_is_directory=True)
    (STATE / 'reports' / (PIN['report_prefix'] + '-extension.json')).write_text(json.dumps({
        'model': PIN['model_id'],
        'backend_digest': PIN['backend_digest'], 'upstream_sha256': digest(backup),
        'patched_sha256': digest(source), 'conversion_module_sha256': digest(BACKEND / 'transcription_conversion.py'),
        'config_sha256': digest(STAGING / configuration),
        'precision': 'float32', 'device': 'cuda', 'opencc': 's2t', 'request_language_forwarded': True,
    }, indent=2) + '\n')
    run(BACKEND / 'run.sh', '--help', cwd=BACKEND)
    print('Prepared. Test with a separate LocalAI process using models path: ' + str(STAGING))


def publish():
    ensure_owner()
    proof = json.loads((STATE / 'reports' / (PIN['report_prefix'] + '-api-8768.json')).read_text())
    model = json.loads((STATE / 'reports' / (PIN['model_id'] + '-model.json')).read_text())
    if (not model['native_backend_load_passed'] or model['model'] != PIN['model_id']
            or model['compute_type'] != 'float32' or model['device'] != 'cuda'
            or model['model_sha256'] != PIN['files']['model.bin']):
        raise RuntimeError('The pinned Whisper model has not passed native CUDA FP32 verification')
    extension = json.loads((STATE / 'reports' / (PIN['report_prefix'] + '-extension.json')).read_text())
    if (not proof['passed'] or proof['model'] != PIN['model_id']
            or proof['model_sha256'] != PIN['files']['model.bin']
            or proof['patched_sha256'] != digest(BACKEND / 'backend.py')):
        raise RuntimeError('The current Whisper backend has not passed staging API tests')
    configuration = STAGING / (PIN['model_id'] + '.yaml')
    if digest(configuration) != extension['config_sha256'] or digest(configuration) != proof['config_sha256']:
        raise RuntimeError('Whisper configuration changed after preparation')
    shutil.copyfile(configuration, STATE / 'models' / configuration.name)
    print('Published ' + PIN['model_id'] + '. Existing startup model and VocaLinux settings are unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'publish'])
    parser.add_argument('--model', choices=WHISPER_MODELS, default='whisper-large-v3')
    options = parser.parse_args()
    PIN = model_pin(options.model)
    (prepare if options.command == 'prepare' else publish)()
