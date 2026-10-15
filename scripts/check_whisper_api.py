"""Check the real LocalAI Whisper API; records facts, not guaranteed ASR accuracy."""
import argparse
import hashlib
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.localai'
sys.path.insert(0, str(ROOT))
from add_whisper import WHISPER_MODELS, model_pin


def post(port, filename, language, model_id='whisper-large-v3'):
    boundary = uuid.uuid4().hex
    body = bytearray()
    fields = {'model': model_id}
    if language is not None:
        fields['language'] = language
    for name, value in fields.items():
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode())
    body.extend((STATE / 'samples' / filename).read_bytes())
    body.extend(f'\r\n--{boundary}--\r\n'.encode())
    request = urllib.request.Request(f'http://127.0.0.1:{port}/v1/audio/transcriptions', data=body,
                                     headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
    text = result['text']
    assert text.strip(), result
    if result.get('segments'):
        assert ''.join(s['text'] for s in result['segments']) == text, result
    if filename == 'chinese.wav' and language != 'en':
        assert '出現' in text and '出现' not in text, result
    if filename == 'english.wav' and language != 'zh':
        assert 'country' in text.lower() and 'americans' in text.lower(), result
    return {'sample': filename, 'language': language, 'text': text,
            'seconds': round(time.perf_counter() - start, 3), 'segments_consistent': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--model', choices=WHISPER_MODELS, default='whisper-large-v3')
    options = parser.parse_args()
    with urllib.request.urlopen(f'http://127.0.0.1:{options.port}/v1/models', timeout=5) as response:
        assert any(m['id'] == options.model for m in json.load(response)['data'])
    results = []
    for filename in ('chinese.wav', 'english.wav', 'mixed.wav'):
        for language in ('zh', 'en', 'auto', None):
            result = post(options.port, filename, language, options.model)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    pins = model_pin(options.model)
    backend_file = STATE / 'backends' / pins['backend_name'] / 'backend.py'
    configuration = STATE / ('whisper-staging/models' if options.port == 8768 else 'models') / (options.model + '.yaml')
    report = {'port': options.port, 'model': options.model, 'passed': True,
              'model_sha256': pins['files']['model.bin'],
              'config_sha256': hashlib.sha256(configuration.read_bytes()).hexdigest(),
              'results': results, 'training_recovered': ['training' in r['text'].lower() for r in results if r['sample'] == 'mixed.wav'],
              'patched_sha256': hashlib.sha256(backend_file.read_bytes()).hexdigest(),
              'limits': 'Only these three short clips and JSON responses are validated; no user microphone recording.'}
    (STATE / f"reports/{pins['report_prefix']}-api-{options.port}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
