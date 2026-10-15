"""Sync canonical Mermaid sources into README, or check for stale copies."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'README.md'
    original = text = path.read_text()
    for source in sorted((ROOT / 'diagrams').glob('*.mmd')):
        begin = '<!-- diagram:' + source.stem + ':start -->'
        end = '<!-- diagram:' + source.stem + ':end -->'
        assert text.count(begin) == text.count(end) == 1, 'Missing/duplicate diagram markers: ' + source.name
        body = source.read_text().strip()
        assert body.startswith('flowchart '), source.name
        start, finish = text.index(begin), text.index(end) + len(end)
        text = text[:start] + begin + '\n```mermaid\n' + body + '\n```\n' + end + text[finish:]
    if args.check:
        if text != original:
            raise SystemExit('README diagrams are stale; run python3 scripts/diagrams.py')
        print('PASS: README diagrams match diagrams/*.mmd')
    else:
        path.write_text(text)
        print('README diagrams synchronized')


if __name__ == '__main__':
    main()
