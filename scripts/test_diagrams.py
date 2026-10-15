"""Verify the README synchronization gate rejects stale and missing diagram blocks."""
import sys
import tempfile
from pathlib import Path
import diagrams

with tempfile.TemporaryDirectory() as directory:
    diagrams.ROOT = Path(directory)
    source = diagrams.ROOT / 'diagrams'
    source.mkdir()
    (source / 'test.mmd').write_text('flowchart TD\n A --> B\n')
    readme = diagrams.ROOT / 'README.md'
    readme.write_text('<!-- diagram:test:start -->\nstale\n<!-- diagram:test:end -->\n')
    sys.argv = ['diagrams.py', '--check']
    try:
        diagrams.main()
    except SystemExit as error:
        assert 'stale' in str(error)
    else:
        raise AssertionError('Accepted stale README diagram')
    sys.argv = ['diagrams.py']
    diagrams.main()
    sys.argv = ['diagrams.py', '--check']
    diagrams.main()
    readme.write_text('missing markers')
    try:
        diagrams.main()
    except AssertionError as error:
        assert 'markers' in str(error)
    else:
        raise AssertionError('Accepted missing markers')
print('PASS: diagram gate rejects stale copies and missing markers')
