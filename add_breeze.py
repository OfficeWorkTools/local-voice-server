#!/usr/bin/env python3
"""Prepare official Breeze sources and CPU INT8 conversions; publish after tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from deploy import ROOT, STATE, PINS, digest, download, ensure_owner, run

PIN = PINS['breeze_cpu']
BACKEND = STATE / 'backends' / PIN['backend_name']
BASE = STATE / 'backends/cpu-funasr'
PYTHON = BACKEND / 'venv/bin/python'
STAGING = STATE / 'breeze-staging/models'
REPORT = STATE / 'reports'


def prepare():
    ensure_owner()
    os.environ.update(PIP_CACHE_DIR=str(STATE / 'cache/breeze-pip'), CUDA_VISIBLE_DEVICES='',
                      OMP_NUM_THREADS='8', MKL_NUM_THREADS='8', HF_HUB_OFFLINE='1')
    if json.loads((BASE / 'metadata.json').read_text())['digest'] != PINS['backend']['digest']:
        raise RuntimeError('Install the pinned CPU base runtime first')
    BACKEND.mkdir(parents=True, exist_ok=True)
    if not PYTHON.exists():
        run(BASE / 'python/bin/python3', '-m', 'venv', BACKEND / 'venv')
    installed = {p['name'].lower(): p['version'] for p in json.loads(subprocess.check_output([str(PYTHON), '-m', 'pip', 'list', '--format=json']))}
    if any(installed.get(name.lower()) != version for name, version in PIN['packages'].items()):
        run(PYTHON, '-m', 'pip', 'install', '--index-url', 'https://download.pytorch.org/whl/cpu', 'torch==' + PIN['packages']['torch'])
        run(PYTHON, '-m', 'pip', 'install', *(name + '==' + version for name, version in PIN['packages'].items() if name != 'torch'))
    run(PYTHON, '-m', 'pip', 'check')
    for name, sha in PINS['modern_cpu_asr']['protocol_files'].items():
        if digest(BASE / name) != sha:
            raise RuntimeError('Original CPU protocol helper changed: ' + name)
        (BACKEND / name).parent.mkdir(exist_ok=True)
        shutil.copyfile(BASE / name, BACKEND / name)
    code = BACKEND / 'backend.py'
    extension = REPORT / 'breeze-extension.json'
    if code.exists() and (not extension.exists() or digest(code) != json.loads(extension.read_text())['backend_sha256']):
        raise RuntimeError('Refusing to overwrite unknown Breeze backend edits')
    shutil.copyfile(ROOT / 'scripts/breeze_backend.py', code)
    shutil.copyfile(ROOT / 'scripts/transcription_conversion.py', BACKEND / 'transcription_conversion.py')
    link = BACKEND / 'opencc'
    if link.is_symlink():
        if link.resolve() != (STATE / 'conversion/opencc').resolve():
            raise RuntimeError('Unexpected OpenCC link')
    elif link.exists():
        raise RuntimeError('Refusing to replace OpenCC directory')
    else:
        link.symlink_to('../../conversion/opencc', target_is_directory=True)
    launcher = BACKEND / 'run.sh'
    launcher.write_text('#!/bin/bash\nset -e\nDIR="$(cd "$(dirname "$0")" && pwd)"\n'
        'export LOCALAI_ASR_ROOT="$(cd "$DIR/../../.." && pwd)"\n'
        'export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 HF_HUB_OFFLINE=1\n'
        'export HF_HOME="$LOCALAI_ASR_ROOT/.localai/cache/breeze-hf"\n'
        'exec "$DIR/venv/bin/python" "$DIR/backend.py" "$@"\n')
    launcher.chmod(0o755)
    (BACKEND / 'metadata.json').write_text(json.dumps({'name': PIN['backend_name'], 'alias': PIN['backend_alias'],
        'uri': 'local:breeze_backend.py', 'digest': 'sha256:' + digest(code)}, indent=2) + '\n')
    STAGING.mkdir(parents=True, exist_ok=True)
    for model_id, profile in PIN['profiles'].items():
        source = STATE / 'models' / profile['source_directory']
        for name, sha in profile['files'].items():
            download(f"https://huggingface.co/{profile['repo']}/resolve/{profile['revision']}/{name}", source / name, sha)
        target = STATE / 'models' / profile['directory']
        if not target.exists():
            with tempfile.TemporaryDirectory(prefix=profile['directory'], dir=STATE / 'models') as temporary:
                converted = Path(temporary) / 'converted'
                run(PYTHON.parent / 'ct2-transformers-converter', '--model', source, '--output_dir', converted,
                    '--copy_files', 'preprocessor_config.json', '--quantization', 'int8')
                run(PYTHON, '-c', 'import sys; from transformers import AutoTokenizer; '
                    'AutoTokenizer.from_pretrained(sys.argv[1], local_files_only=True).backend_tokenizer.save(sys.argv[2])',
                    source, converted / 'tokenizer.json')
                if {name: digest(converted / name) for name in profile['converted_files']} != profile['converted_files']:
                    raise RuntimeError('Converted Breeze hashes differ from pinned conversion')
                converted.rename(target)
        for name, sha in profile['converted_files'].items():
            if digest(target / name) != sha:
                raise RuntimeError('Unknown converted Breeze file: ' + name)
        link = STAGING / profile['directory']
        if link.is_symlink():
            if link.resolve() != target.resolve():
                raise RuntimeError('Unexpected staged Breeze link')
        elif link.exists():
            raise RuntimeError('Refusing to replace staged Breeze data')
        else:
            link.symlink_to(target.resolve(), target_is_directory=True)
        shutil.copyfile(ROOT / 'config' / (model_id + '.yaml'), STAGING / (model_id + '.yaml'))
    sample = PIN['taigi_sample']
    archive_path = STATE / 'downloads/breeze-taigi.zip'
    download(sample['url'], archive_path, sample['zip_sha256'])
    with zipfile.ZipFile(archive_path) as archive:
        audio = archive.read(sample['member'])
    if hashlib.sha256(audio).hexdigest() != sample['mp3_sha256']:
        raise RuntimeError('Official Taigi sample checksum mismatch')
    mp3 = STATE / 'samples/breeze-taigi-source.mp3'
    mp3.write_bytes(audio)
    run('ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', mp3, '-t', '8', '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', STATE / 'samples/taigi.wav')
    extension.write_text(json.dumps({'backend_sha256': digest(code), 'launcher_sha256': digest(launcher),
        'conversion_sha256': digest(BACKEND / 'transcription_conversion.py'), 'packages': PIN['packages'],
        'base_backend_digest': PINS['backend']['digest'], 'device': 'cpu', 'compute_type': 'int8',
        'taigi_excerpt_seconds': 8}, indent=2) + '\n')
    print('Prepared Breeze 25 and 26 in ' + str(STAGING))


def publish():
    ensure_owner()
    for model_id, profile in PIN['profiles'].items():
        model = json.loads((REPORT / (profile['report_prefix'] + '-model.json')).read_text())
        api = json.loads((REPORT / (profile['report_prefix'] + '-api-8768.json')).read_text())
        config = STAGING / (model_id + '.yaml')
        if (not api['passed'] or api['model'] != model_id or api['config_sha256'] != digest(config)
                or api['backend_sha256'] != digest(BACKEND / 'backend.py') or not model['native_backend_load_passed']
                or model['model'] != model_id or model['device'] != 'cpu' or model['compute_type'] not in ('int8', 'int8_float32')
                or model['source_files_sha256'] != profile['files'] or model['converted_files_sha256'] != profile['converted_files']
                or model['packages'] != PIN['packages'] or model['backend_sha256'] != digest(BACKEND / 'backend.py')):
            raise RuntimeError('Missing current CPU INT8/API evidence for ' + model_id)
    for model_id in PIN['profiles']:
        shutil.copyfile(STAGING / (model_id + '.yaml'), STATE / 'models' / (model_id + '.yaml'))
    print('Published: ' + ', '.join(PIN['profiles']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'publish'])
    args = parser.parse_args()
    (prepare if args.command == 'prepare' else publish)()
