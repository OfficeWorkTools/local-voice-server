"""Validate installed CPU ASR profiles through the same Local Voice API."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
from check_whisper_api import post

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.localai'
PINS = json.loads((ROOT / 'config/versions.json').read_text())['modern_cpu_asr']
NANO = json.loads((ROOT / 'config/versions.json').read_text())['nano_hf']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--model', choices=[*PINS['profiles'], NANO['model_id']], required=True)
    args = parser.parse_args()
    is_nano = args.model == NANO['model_id']
    profile = NANO if is_nano else PINS['profiles'][args.model]
    with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/v1/models', timeout=10) as response:
        assert args.model in {m['id'] for m in json.load(response)['data']}
    modes = ['auto', None] if profile.get('engine') == 'firered' else ['zh', 'en', 'auto', None]
    results = []
    for filename in ('chinese.wav', 'english.wav', 'mixed.wav'):
        for mode in modes:
            result = post(args.port, filename, mode, args.model)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    staging = 'nano-hf-staging/models' if is_nano else 'modern-cpu-staging/models'
    config = STATE / (staging if args.port == 8768 else 'models') / (args.model + '.yaml')
    backend = STATE / 'backends' / (NANO if is_nano else PINS)['backend_name'] / 'backend.py'
    report = {'model': args.model, 'port': args.port, 'passed': True, 'results': results,
              'config_sha256': hashlib.sha256(config.read_bytes()).hexdigest(),
              'backend_sha256': hashlib.sha256(backend.read_bytes()).hexdigest(),
              'limits': 'Short CPU API integration checks, not user microphone accuracy or streaming latency.'}
    prefix = 'nano-hf' if is_nano else args.model
    (STATE / 'reports' / f'{prefix}-api-{args.port}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
