#!/usr/bin/env python3
"""Prepare fixed CPU ASR profiles, test privately, then publish verified YAMLs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tarfile
import zipfile
from deploy import ROOT, STATE, PINS, digest, download, ensure_owner, run

PIN = PINS['modern_cpu_asr']
BACKEND = STATE / 'backends' / PIN['backend_name']
BASE = STATE / 'backends/cpu-funasr'
STAGING = STATE / 'modern-cpu-staging/models'


def prepare():
    ensure_owner()
    if json.loads((BASE / 'metadata.json').read_text())['digest'] != PINS['backend']['digest']:
        raise RuntimeError('Install the pinned original CPU FunASR runtime first')
    native_pin = PIN['audio_cpp']
    native = STATE / 'backends' / native_pin['backend_name']
    if not (native / 'metadata.json').exists():
        run(STATE / 'bin/local-ai', 'backends', 'install', native_pin['uri'], native_pin['backend_name'], native_pin['backend_alias'],
            '--backend-galleries=[]', '--backends-path', STATE / 'backends', cwd=STATE)
    if json.loads((native / 'metadata.json').read_text())['digest'] != native_pin['digest']:
        raise RuntimeError('Native audio.cpp digest mismatch')
    BACKEND.mkdir(parents=True, exist_ok=True)
    for name, expected in PIN['protocol_files'].items():
        if digest(BASE / name) != expected:
            raise RuntimeError('Original CPU protocol helper changed: ' + name)
        (BACKEND / name).parent.mkdir(exist_ok=True)
        shutil.copyfile(BASE / name, BACKEND / name)
    wheel = STATE / 'downloads/fbank.whl'
    download(PIN['fbank']['url'], wheel, PIN['fbank']['sha256'])
    vendor = BACKEND / 'vendor'
    vendor.mkdir(exist_ok=True)
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise RuntimeError('Unsafe wheel member')
        archive.extractall(vendor)
    for name, pin in PIN.get('sherpa_wheels', {}).items():
        wheel = STATE / 'downloads' / (name + '.whl')
        download(pin['url'], wheel, pin['sha256'])
        with zipfile.ZipFile(wheel) as archive:
            if any(Path(n).is_absolute() or '..' in Path(n).parts for n in archive.namelist()):
                raise RuntimeError('Unsafe Sherpa wheel member')
            archive.extractall(vendor)
    source_pin = PIN['firered_source']
    archive_path = STATE / 'downloads/firered-source.tar.gz'
    download(source_pin['url'], archive_path, source_pin['sha256'])
    source = BACKEND / 'firered-source'
    source.mkdir(exist_ok=True)
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            if member.isfile() and (source / member.name).exists():
                if (source / member.name).read_bytes() != archive.extractfile(member).read():
                    raise RuntimeError('Refusing to overwrite edited FireRed source: ' + member.name)
        archive.extractall(source, filter='data')
    code = BACKEND / 'backend.py'
    report_file = STATE / 'reports/modern-cpu-extension.json'
    if code.exists() and report_file.exists():
        if digest(code) != json.loads(report_file.read_text())['backend_sha256']:
            raise RuntimeError('Refusing to overwrite unknown CPU backend edits')
    shutil.copyfile(ROOT / 'scripts/cpu_asr_backend.py', code)
    shutil.copyfile(ROOT / 'scripts/transcription_conversion.py', BACKEND / 'transcription_conversion.py')
    link = BACKEND / 'opencc'
    if not link.is_symlink():
        if link.exists():
            raise RuntimeError('Refusing to replace OpenCC directory')
        link.symlink_to('../../conversion/opencc', target_is_directory=True)
    elif link.resolve() != (STATE / 'conversion/opencc').resolve():
        raise RuntimeError('Unexpected OpenCC link')
    launcher = BACKEND / 'run.sh'
    launcher.write_text('#!/bin/bash\nset -e\nDIR="$(cd "$(dirname "$0")" && pwd)"\n'
        'export LOCALAI_ASR_ROOT="$(cd "$DIR/../../.." && pwd)"\n'
        'export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=8 MKL_NUM_THREADS=8\n'
        'exec "$DIR/../cpu-funasr/venv/bin/python" "$DIR/backend.py" "$@"\n')
    launcher.chmod(0o755)
    (BACKEND / 'metadata.json').write_text(json.dumps({'name': PIN['backend_name'], 'alias': PIN['backend_alias'],
        'uri': 'local:cpu_asr_backend.py', 'digest': 'sha256:' + digest(code)}, indent=2) + '\n')
    STAGING.mkdir(parents=True, exist_ok=True)
    for model_id, profile in PIN['profiles'].items():
        model = STATE / 'models' / profile['directory']
        if 'archive' in profile and not all((model / n).is_file() and digest(model / n) == sha for n, sha in profile['files'].items()):
            archive_pin = profile['archive']
            archive_path = STATE / 'downloads/sensevoice-onnx.tar.bz2'
            download(archive_pin['url'], archive_path, archive_pin['sha256'])
            model.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_path, mode='r|bz2') as archive:
                for member in archive:
                    name = member.name.removeprefix(archive_pin['prefix'] + '/')
                    if name in profile['files'] and member.isfile():
                        temporary = model / (name + '.part')
                        with archive.extractfile(member) as source, temporary.open('wb') as target:
                            shutil.copyfileobj(source, target)
                        if digest(temporary) != profile['files'][name]:
                            raise RuntimeError('SenseVoice ONNX member checksum mismatch')
                        temporary.replace(model / name)
        for filename, expected in profile['files'].items():
            target = model if profile['engine'] == 'audio-cpp' else model / filename
            if 'archive' not in profile:
                download(f"https://huggingface.co/{profile['repo']}/resolve/{profile['revision']}/{filename}", target, expected)
            elif not target.is_file() or digest(target) != expected:
                raise RuntimeError('Missing verified ONNX export member: ' + filename)
        stage = STAGING / profile['directory']
        stage.parent.mkdir(parents=True, exist_ok=True)
        if stage.is_symlink():
            if stage.resolve() != model.resolve():
                raise RuntimeError('Unexpected staged model link')
        elif stage.exists():
            raise RuntimeError('Refusing to replace staged data')
        else:
            stage.symlink_to(model.resolve(), target_is_directory=profile['engine'] != 'audio-cpp')
        shutil.copyfile(ROOT / 'config' / (model_id + '.yaml'), STAGING / (model_id + '.yaml'))
    report_file.write_text(json.dumps({'backend_sha256': digest(code), 'launcher_sha256': digest(launcher),
        'conversion_sha256': digest(BACKEND / 'transcription_conversion.py'),
        'audio_cpp_digest': native_pin['digest'], 'firered_source_sha256': source_pin['sha256'],
        'fbank_wheel_sha256': PIN['fbank']['sha256'], 'cpu_only': True}, indent=2) + '\n')
    print('Prepared CPU profiles in ' + str(STAGING))


def publish():
    ensure_owner()
    for model_id, profile in PIN['profiles'].items():
        proof = json.loads((STATE / 'reports' / (model_id + '-api-8768.json')).read_text())
        native = json.loads((STATE / 'reports' / (model_id + '-model.json')).read_text())
        config = STAGING / (model_id + '.yaml')
        if (not proof['passed'] or proof['model'] != model_id or proof['backend_sha256'] != digest(BACKEND / 'backend.py')
                or proof['config_sha256'] != digest(config) or not native['native_backend_load_passed']
                or native['model'] != model_id or native['device'] != 'cpu' or not native['files_verified']
                or native['files_sha256'] != profile['files'] or native['backend_sha256'] != digest(BACKEND / 'backend.py')):
            raise RuntimeError('Missing current native CPU/API evidence for ' + model_id)
    for model_id in PIN['profiles']:
        shutil.copyfile(STAGING / (model_id + '.yaml'), STATE / 'models' / (model_id + '.yaml'))
    print('Published: ' + ', '.join(PIN['profiles']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'publish'])
    options = parser.parse_args()
    (prepare if options.command == 'prepare' else publish)()
