#!/usr/bin/env -S uv run --python 3.11
"""Hashdeep snapshots; semantic ingestion remains the agent's responsibility."""
import argparse
import fnmatch
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

SKIP = {'.git', '.Glossary-Wiki', 'node_modules', '.venv', '__pycache__'}
CATALOG = Path(__file__).resolve().parents[1] / 'catalog'
CHUNK_SIZE = 64
MAX_ARG_CHARS = 8000


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.writing-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def lock(state: Path) -> Iterator[None]:
    marker = state / 'changes.lock'
    fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        marker.unlink()


def matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern) or (
        pattern.startswith('**/') and fnmatch.fnmatchcase(path, pattern[3:]))


def validate_scope(scope: Any) -> dict[str, Any]:
    if not isinstance(scope, dict):
        raise ValueError('scope.json must contain an object')
    for key in ('include', 'exclude'):
        if key == 'exclude' and key not in scope:
            continue
        value = scope.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f'scope.json {key} must be a list of glob strings')
    if not scope['include']:
        raise ValueError('scope.json needs a nonempty include list')
    return scope


def inventory(root: Path, scope: Any) -> list[str]:
    scope = validate_scope(scope)
    paths = []
    def failed(error):
        raise error
    for base, dirs, files in os.walk(root, followlinks=False, onerror=failed):
        directory = Path(base)
        dirs[:] = sorted(d for d in dirs if d not in SKIP
                          and (directory / d) != CATALOG
                          and not (directory / d).is_symlink()
                          and not (directory / d / '.Glossary-Wiki').is_dir())
        for name in sorted(files):
            path = directory / name
            relative = path.relative_to(root).as_posix()
            if name == '.ftag' or path.is_symlink() or not path.is_file():
                continue
            if any(c in relative for c in '\n\r'):
                raise ValueError('Newline filenames require manual handling: ' + repr(relative))
            if any(matches(relative, p) for p in scope['include']) and not any(
                    matches(relative, p) for p in scope.get('exclude', [])):
                paths.append(relative)
    return sorted(paths)


def chunks(paths: list[str]) -> Iterator[list[str]]:
    chunk: list[str] = []
    size = 0
    for path in paths:
        length = len(path) + 3  # './' prefix and separator
        if chunk and (len(chunk) == CHUNK_SIZE or size + length > MAX_ARG_CHARS):
            yield chunk
            chunk, size = [], 0
        chunk.append(path)
        size += length
    if chunk:
        yield chunk


def hashdeep_chunk(binary: str, root: Path, paths: list[str]) -> dict[str, dict[str, Any]]:
    arguments = ['./' + path for path in paths]
    result = subprocess.run([binary, '-c', 'sha256', '-l', *arguments],
                            cwd=root, capture_output=True, text=True)
    # Exit status is authoritative; some builds print harmless warnings to stderr.
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f'exit code {result.returncode}'
        raise RuntimeError('hashdeep failed: ' + detail)
    rows = {}
    # Split on newline only: splitlines() also breaks on U+2028/U+0085,
    # which are legal in filenames.
    for line in result.stdout.split('\n'):
        match = re.match(r'^(\d+),([0-9a-fA-F]{64}),(.+?)\r?$', line)
        if match:
            size, digest, name = match.groups()
            rows[name] = {'size': int(size), 'sha256': digest.lower()}
    expected = set(arguments)
    missing = expected - rows.keys()
    if missing or rows.keys() - expected:
        names = sorted(missing or rows.keys() - expected)
        detail = result.stderr.strip()
        message = 'Unexpected hashdeep output for ' + ', '.join(names)
        raise ValueError(message + (': ' + detail if detail else ''))
    return {path: rows['./' + path] for path in paths}


def snapshot(root: Path, scope: Any) -> dict[str, dict[str, Any]]:
    binary = shutil.which('hashdeep')
    if not binary:
        raise RuntimeError('hashdeep unavailable; no baseline was advanced')
    paths = inventory(root, scope)
    records: dict[str, dict[str, Any]] = {}
    for chunk in chunks(paths):
        try:
            records.update(hashdeep_chunk(binary, root, chunk))
        except ValueError:
            # Rows already name the affected files; retrying would only rehash healthy ones.
            raise
        except RuntimeError:
            if len(chunk) == 1:
                raise
            # Isolate a failing process so the error names the file.
            for path in chunk:
                records.update(hashdeep_chunk(binary, root, [path]))
    if inventory(root, scope) != paths:
        raise RuntimeError('Inventory changed during scan; retry')
    return records


def delta(before: dict[str, dict[str, Any]],
          after: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    return {'added': sorted(after.keys() - before.keys()),
            'changed': sorted(p for p in after.keys() & before.keys() if after[p] != before[p]),
            'removed': sorted(before.keys() - after.keys())}


def run(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve(strict=True)
    state = root / '.Glossary-Wiki' / 'state'
    if not state.is_dir():
        raise ValueError('Initialize .Glossary-Wiki/state and scope.json first')
    if (root / '.Glossary-Wiki').is_symlink() or state.is_symlink():
        raise ValueError('Wiki and state must be local directories')
    with lock(state):
        scope = read_json(state / 'scope.json')
        previous = read_json(state / 'manifest.json', {})
        if args.command == 'scan':
            current = snapshot(root, scope)
            changes = delta(previous, current)
            atomic_json(state / 'pending.json', {'schema_version': 1, 'base': previous,
                                                 'scope': scope, 'files': current, 'delta': changes})
            print(json.dumps(changes, ensure_ascii=False, indent=2))
        else:
            if not args.reviewed:
                raise ValueError('commit requires --reviewed after all pending work is completed')
            pending = read_json(state / 'pending.json')
            if pending is None:
                raise ValueError('No pending scan')
            if previous != pending['base'] or scope != pending['scope']:
                raise ValueError('Baseline or scope changed; scan again')
            current = snapshot(root, scope)
            if current != pending['files']:
                raise ValueError('Sources changed after scan; ingest a fresh scan before commit')
            # manifest is authoritative. The hashdeep export is a rebuildable view.
            exported = '%%%% HASHDEEP-1.0\n%%%% size,sha256,filename\n'
            exported += ''.join(f"{v['size']},{v['sha256']},{p}\n" for p, v in current.items())
            export_tmp = state / 'sources.hashdeep.tmp'
            export_tmp.write_text(exported, encoding='utf-8')
            os.replace(export_tmp, state / 'sources.hashdeep')
            atomic_json(state / 'manifest.json', current)
            (state / 'pending.json').unlink()
            print(json.dumps({'committed': len(current)}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['scan', 'commit'])
    parser.add_argument('root', help='Source directory owning .Glossary-Wiki')
    parser.add_argument('--reviewed', action='store_true', help='All pending changes have been ingested and checked')
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
