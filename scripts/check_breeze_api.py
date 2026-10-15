"""Check CPU Breeze API wiring; Taigi 26 is tested on a public Taigi excerpt."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
from check_whisper_api import post

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.localai'
PIN = json.loads((ROOT / 'config/versions.json').read_text())['breeze_cpu']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--model', choices=PIN['profiles'], required=True)
    args = parser.parse_args()
    profile = PIN['profiles'][args.model]
    with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/v1/models', timeout=10) as response:
        assert args.model in {m['id'] for m in json.load(response)['data']}
    samples = ('chinese.wav', 'english.wav', 'mixed.wav') if args.model == 'breeze-asr-25-cpu' else ('taigi.wav',)
    modes = ('zh', 'en', 'auto', None) if args.model == 'breeze-asr-25-cpu' else ('zh', 'auto', None)
    results = []
    for filename in samples:
        for mode in modes:
            result = post(args.port, filename, mode, args.model)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    config = STATE / ('breeze-staging/models' if args.port == 8768 else 'models') / (args.model + '.yaml')
    report = {'model': args.model, 'port': args.port, 'passed': True, 'results': results,
              'config_sha256': hashlib.sha256(config.read_bytes()).hexdigest(),
              'backend_sha256': hashlib.sha256((STATE / 'backends' / PIN['backend_name'] / 'backend.py').read_bytes()).hexdigest(),
              'limits': 'Short functional tests only; Breeze 26 uses an eight-second Taigi excerpt, no accuracy benchmark.'}
    (STATE / 'reports' / f"{profile['report_prefix']}-api-{args.port}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
