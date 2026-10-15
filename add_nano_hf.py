#!/usr/bin/env python3
"""Install an isolated, pinned native Nano HF CPU runtime and publish after tests."""
import argparse
import json
import os
import shutil
import subprocess
from deploy import ROOT, STATE, PINS, digest, download, ensure_owner, run

PIN = PINS['nano_hf']
BACKEND = STATE / 'backends' / PIN['backend_name']
BASE = STATE / 'backends/cpu-funasr'
PYTHON = BACKEND / 'venv/bin/python'
STAGING = STATE / 'nano-hf-staging/models'
REPORT = STATE / 'reports'


def prepare():
    ensure_owner()
    os.environ['PIP_CACHE_DIR'] = str(STATE / 'cache/nano-hf-pip')
    if json.loads((BASE / 'metadata.json').read_text())['digest'] != PINS['backend']['digest']:
        raise RuntimeError('Install the pinned CPU FunASR base runtime first')
    BACKEND.mkdir(parents=True, exist_ok=True)
    if not PYTHON.exists():
        run(BASE / 'python/bin/python3', '-m', 'venv', BACKEND / 'venv')
    packages = json.loads(subprocess.check_output([str(PYTHON), '-m', 'pip', 'list', '--format=json']))
    installed = {p['name'].lower(): p['version'] for p in packages}
    if any(installed.get(name.lower()) != version for name, version in PIN['packages'].items()):
        run(PYTHON, '-m', 'pip', 'install', '--index-url', 'https://download.pytorch.org/whl/cpu',
            'torch==' + PIN['packages']['torch'], 'torchaudio==' + PIN['packages']['torchaudio'])
        run(PYTHON, '-m', 'pip', 'install', *(name + '==' + version for name, version in PIN['packages'].items()
                                            if name not in ('torch', 'torchaudio')))
    run(PYTHON, '-m', 'pip', 'check')
    for name, expected in PINS['modern_cpu_asr']['protocol_files'].items():
        if digest(BASE / name) != expected:
            raise RuntimeError('Original CPU protocol helper changed: ' + name)
        (BACKEND / name).parent.mkdir(exist_ok=True)
        shutil.copyfile(BASE / name, BACKEND / name)
    code = BACKEND / 'backend.py'
    proof_path = REPORT / 'nano-hf-extension.json'
    if code.exists() and (not proof_path.exists() or digest(code) != json.loads(proof_path.read_text())['backend_sha256']):
        raise RuntimeError('Refusing to overwrite unknown Nano HF backend edits')
    shutil.copyfile(ROOT / 'scripts/nano_hf_backend.py', code)
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
        'export HF_HUB_OFFLINE=1 HF_HOME="$LOCALAI_ASR_ROOT/.localai/cache/nano-hf"\n'
        'exec "$DIR/venv/bin/python" "$DIR/backend.py" "$@"\n')
    launcher.chmod(0o755)
    (BACKEND / 'metadata.json').write_text(json.dumps({'name': PIN['backend_name'], 'alias': PIN['backend_alias'],
        'uri': 'local:nano_hf_backend.py', 'digest': 'sha256:' + digest(code)}, indent=2) + '\n')
    model = STATE / 'models' / PIN['directory']
    for name, expected in PIN['files'].items():
        download(f"https://huggingface.co/{PIN['repo']}/resolve/{PIN['revision']}/{name}", model / name, expected)
    STAGING.mkdir(parents=True, exist_ok=True)
    link = STAGING / PIN['directory']
    if link.is_symlink():
        if link.resolve() != model.resolve():
            raise RuntimeError('Unexpected staged Nano HF link')
    elif link.exists():
        raise RuntimeError('Refusing to replace staged Nano HF data')
    else:
        link.symlink_to(model.resolve(), target_is_directory=True)
    shutil.copyfile(ROOT / 'config' / (PIN['model_id'] + '.yaml'), STAGING / (PIN['model_id'] + '.yaml'))
    proof_path.write_text(json.dumps({'backend_sha256': digest(code), 'launcher_sha256': digest(launcher),
        'conversion_sha256': digest(BACKEND / 'transcription_conversion.py'),
        'base_backend_digest': PINS['backend']['digest'], 'packages': PIN['packages'], 'cpu_only': True}, indent=2) + '\n')
    print('Prepared Nano HF in ' + str(STAGING))


def publish():
    ensure_owner()
    model = json.loads((REPORT / 'nano-hf-model.json').read_text())
    api = json.loads((REPORT / 'nano-hf-api-8768.json').read_text())
    config = STAGING / (PIN['model_id'] + '.yaml')
    if (not api['passed'] or api['model'] != PIN['model_id'] or api['config_sha256'] != digest(config)
            or api['backend_sha256'] != digest(BACKEND / 'backend.py')
            or not model['native_backend_load_passed'] or model['model'] != PIN['model_id']
            or model['engine_class'] != 'FunAsrNanoForConditionalGeneration' or model['device'] != 'cpu'
            or model['parameter_dtypes'] != ['torch.float32'] or model['files_sha256'] != PIN['files']
            or model['packages'] != PIN['packages'] or model['backend_sha256'] != digest(BACKEND / 'backend.py')):
        raise RuntimeError('Missing current native CPU FP32/API evidence for Nano HF')
    shutil.copyfile(config, STATE / 'models' / config.name)
    print('Published ' + PIN['model_id'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'publish'])
    options = parser.parse_args()
    (prepare if options.command == 'prepare' else publish)()
