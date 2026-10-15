"""Check profile isolation and prevent publishing a different model's evidence."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import add_whisper as installer

full = installer.model_pin('whisper-large-v3')
turbo = installer.model_pin('whisper-large-v3-turbo')
assert full['directory'] != turbo['directory']
assert full['files']['model.bin'] != turbo['files']['model.bin']
assert full['backend_digest'] == turbo['backend_digest']

with tempfile.TemporaryDirectory() as directory:
    installer.STATE = Path(directory)
    installer.STAGING = installer.STATE / 'staging'
    installer.BACKEND = installer.STATE / 'backend'
    installer.ensure_owner = lambda: None
    for path in (installer.STAGING, installer.BACKEND, installer.STATE / 'reports', installer.STATE / 'models'):
        path.mkdir(parents=True)
    backend = installer.BACKEND / 'backend.py'
    backend.write_text('test backend')
    for pin in (full, turbo):
        installer.PIN = pin
        config = installer.STAGING / (pin['model_id'] + '.yaml')
        config.write_text('name: ' + pin['model_id'] + '\n')
        model = {'model': pin['model_id'], 'native_backend_load_passed': True, 'compute_type': 'float32',
                 'device': 'cuda', 'model_sha256': pin['files']['model.bin']}
        proof = {'model': pin['model_id'], 'passed': True, 'model_sha256': pin['files']['model.bin'],
                 'patched_sha256': installer.digest(backend), 'config_sha256': installer.digest(config)}
        report = installer.STATE / 'reports'
        (report / (pin['model_id'] + '-model.json')).write_text(json.dumps(model))
        (report / (pin['report_prefix'] + '-extension.json')).write_text(json.dumps({'config_sha256': installer.digest(config)}))
        evidence = report / (pin['report_prefix'] + '-api-8768.json')
        evidence.write_text(json.dumps(proof))
        installer.publish()
        destination = installer.STATE / 'models' / config.name
        assert destination.read_bytes() == config.read_bytes()
        for field, wrong in [('model', 'another-model'), ('model_sha256', 'wrong hash'), ('config_sha256', 'changed config')]:
            evidence.write_text(json.dumps({**proof, field: wrong}))
            try:
                installer.publish()
            except RuntimeError:
                pass
            else:
                raise AssertionError('Accepted invalid API evidence: ' + field)
            assert destination.read_bytes() == config.read_bytes()

print('PASS: full and turbo profiles publish separately and reject mismatched evidence')
