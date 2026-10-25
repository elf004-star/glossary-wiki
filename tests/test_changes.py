import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/glossary-wiki/scripts/changes.py'
spec = importlib.util.spec_from_file_location('changes', SCRIPT)
changes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(changes)


class FakeHashdeep:
    def __init__(self, stderr=''):
        self.stderr = stderr
        self.calls = []

    def __call__(self, argv, cwd, **kwargs):
        assert argv[1:4] == ['-c', 'sha256', '-l'], argv
        paths = argv[4:]
        self.calls.append(paths)
        rows = '%%%% HASHDEEP-1.0\n%%%% size,sha256,filename\n'
        for path in paths:
            content = (Path(cwd) / path).read_bytes()
            rows += f'{len(content)},{hashlib.sha256(content).hexdigest()},{path}\n'
        return subprocess.CompletedProcess(argv, 0, rows, self.stderr)


class ChangesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / '.Glossary-Wiki/state'
        self.state.mkdir(parents=True)
        changes.atomic_json(self.state / 'scope.json', {'include': ['**/*.md'], 'exclude': ['vendor/**']})
        self.hashdeep = FakeHashdeep()

    def invoke(self, command, reviewed=False):
        with patch.object(changes.shutil, 'which', return_value='/test/hashdeep'), \
             patch.object(changes.subprocess, 'run', side_effect=self.hashdeep), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            changes.run(types.SimpleNamespace(command=command, root=str(self.root), reviewed=reviewed))
        return json.loads(output.getvalue())

    def test_unicode_comma_and_incremental_commit(self):
        path = self.root / '中文, 空格.md'
        path.write_text('甲', encoding='utf-8')
        self.assertEqual(self.invoke('scan')['added'], [path.name])
        self.assertFalse((self.state / 'manifest.json').exists())
        self.invoke('commit', True)
        self.assertEqual(self.invoke('scan'), {'added': [], 'changed': [], 'removed': []})
        path.write_text('乙', encoding='utf-8')
        self.assertEqual(self.invoke('scan')['changed'], [path.name])
        self.invoke('commit', True)
        path.unlink()
        self.assertEqual(self.invoke('scan')['removed'], [path.name])

    def test_interrupted_scan_remains_added(self):
        (self.root / 'a.md').write_text('a')
        self.invoke('scan')
        self.assertEqual(self.invoke('scan')['added'], ['a.md'])

    def test_changed_after_scan_rejected(self):
        (self.root / 'a.md').write_text('a')
        self.invoke('scan')
        (self.root / 'a.md').write_text('b')
        with self.assertRaisesRegex(ValueError, 'Sources changed'):
            self.invoke('commit', True)
        self.assertFalse((self.state / 'manifest.json').exists())
        self.assertTrue((self.state / 'pending.json').exists())

    def test_boundaries_exclusions_and_symlinks(self):
        for directory in ['child/.Glossary-Wiki', 'vendor', 'normal', 'node_modules']:
            (self.root / directory).mkdir(parents=True)
        for name in ['child/a.md', 'vendor/a.md', 'normal/a.md', 'node_modules/a.md']:
            (self.root / name).write_text('a')
        (self.root / 'linked.md').symlink_to(self.root / 'normal/a.md')
        self.assertEqual(self.invoke('scan')['added'], ['normal/a.md'])

    def test_identical_contents_preserve_path_identity(self):
        (self.root / 'a.md').write_text('same')
        (self.root / 'b.md').write_text('same')
        self.invoke('scan')
        self.invoke('commit', True)
        (self.root / 'a.md').rename(self.root / 'c.md')
        self.assertEqual(self.invoke('scan'), {'added': ['c.md'], 'changed': [], 'removed': ['a.md']})

    def test_scope_change_rejected(self):
        self.invoke('scan')
        changes.atomic_json(self.state / 'scope.json', {'include': ['**/*.txt']})
        with self.assertRaisesRegex(ValueError, 'scope changed'):
            self.invoke('commit', True)

    def test_missing_tool_preserves_baseline(self):
        with patch.object(changes.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                changes.snapshot(self.root, {'include': ['**/*.md']})
        self.assertFalse((self.state / 'manifest.json').exists())

    def test_review_and_lock_required(self):
        self.invoke('scan')
        with self.assertRaisesRegex(ValueError, 'reviewed'):
            self.invoke('commit')
        (self.state / 'changes.lock').write_text('123')
        with self.assertRaises(FileExistsError):
            self.invoke('scan')

    def test_hashdeep_called_in_batches(self):
        for index in range(150):
            (self.root / f'f{index}.md').write_text(str(index))
        self.invoke('scan')
        self.assertEqual(len(self.hashdeep.calls), -(-150 // changes.CHUNK_SIZE))
        self.assertEqual(sorted(p for call in self.hashdeep.calls for p in call),
                         sorted(f'./f{index}.md' for index in range(150)))

    def test_hashdeep_stderr_warning_is_not_failure(self):
        (self.root / 'a.md').write_text('a')
        self.hashdeep = FakeHashdeep(stderr='hashdeep.exe: WARNING: 32-bit program on 64-bit system')
        self.assertEqual(self.invoke('scan')['added'], ['a.md'])

    def test_scope_must_be_object_with_string_lists(self):
        changes.atomic_json(self.state / 'scope.json', ['**/*.md'])
        with self.assertRaisesRegex(ValueError, 'scope.json'):
            self.invoke('scan')
        changes.atomic_json(self.state / 'scope.json', {'include': ['**/*.md'], 'exclude': 'vendor'})
        with self.assertRaisesRegex(ValueError, 'scope.json'):
            self.invoke('scan')
        changes.atomic_json(self.state / 'scope.json', {'include': ['**/*.md'], 'exclude': None})
        with self.assertRaisesRegex(ValueError, 'scope.json'):
            self.invoke('scan')
        changes.atomic_json(self.state / 'scope.json', {})
        with self.assertRaisesRegex(ValueError, 'scope.json'):
            self.invoke('scan')
        changes.atomic_json(self.state / 'scope.json', {'exclude': []})
        with self.assertRaisesRegex(ValueError, 'scope.json'):
            self.invoke('scan')

    def test_missing_exclude_key_is_allowed(self):
        changes.atomic_json(self.state / 'scope.json', {'include': ['**/*.md']})
        (self.root / 'a.md').write_text('a')
        self.assertEqual(self.invoke('scan')['added'], ['a.md'])

    def test_line_separators_inside_filenames(self):
        for name in ['a b.md', 'c\u0085d.md']:
            (self.root / name).write_text('x')
        self.assertEqual(self.invoke('scan')['added'], ['a b.md', 'c\u0085d.md'])

    def test_chunks_respect_character_budget(self):
        paths = ['a' * 20, 'b' * 20, 'c' * 20]
        with patch.object(changes, 'MAX_ARG_CHARS', 50):
            self.assertEqual([len(chunk) for chunk in changes.chunks(paths)], [2, 1])
        with patch.object(changes, 'MAX_ARG_CHARS', 10):
            self.assertEqual([len(chunk) for chunk in changes.chunks(paths)], [1, 1, 1])

    def test_failed_batch_reports_individual_failure(self):
        (self.root / 'a.md').write_text('a')
        (self.root / 'b.md').write_text('b')
        single = FakeHashdeep()

        def flaky(argv, cwd, **kwargs):
            if len(argv) > 5:
                return subprocess.CompletedProcess(argv, 1, '', 'batch failed')
            if argv[-1].endswith('b.md'):
                return subprocess.CompletedProcess(argv, 1, '', 'b.md: locked')
            return single(argv, cwd, **kwargs)

        self.hashdeep = flaky
        with self.assertRaisesRegex(RuntimeError, 'b.md: locked'):
            self.invoke('scan')

    def test_missing_row_includes_hashdeep_stderr(self):
        (self.root / 'a.md').write_text('a')

        def missing(argv, cwd, **kwargs):
            return subprocess.CompletedProcess(argv, 0, '%%%% HASHDEEP-1.0\n', './a.md: No such file')

        self.hashdeep = missing
        with self.assertRaisesRegex(ValueError, 'No such file'):
            self.invoke('scan')

    def test_missing_row_in_batch_does_not_rehash_healthy_files(self):
        (self.root / 'a.md').write_text('a')
        (self.root / 'b.md').write_text('b')
        calls = []

        def partial(argv, cwd, **kwargs):
            calls.append(argv[4:])
            rows = '%%%% HASHDEEP-1.0\n'
            for path in argv[4:]:
                if path != './b.md':
                    content = (Path(cwd) / path).read_bytes()
                    rows += f'{len(content)},{hashlib.sha256(content).hexdigest()},{path}\n'
            return subprocess.CompletedProcess(argv, 0, rows, './b.md: Permission denied')

        self.hashdeep = partial
        with self.assertRaisesRegex(ValueError, 'Permission denied'):
            self.invoke('scan')
        self.assertEqual(len(calls), 1)

    def test_failed_batch_falls_back_to_individual_files(self):
        (self.root / 'a.md').write_text('a')
        (self.root / 'b.md').write_text('b')
        single = FakeHashdeep()

        def flaky(argv, cwd, **kwargs):
            if len(argv) > 5:
                return subprocess.CompletedProcess(argv, 1, '', 'batch failed')
            return single(argv, cwd, **kwargs)

        self.hashdeep = flaky
        self.assertEqual(self.invoke('scan')['added'], ['a.md', 'b.md'])

    @unittest.skipUnless(shutil.which('hashdeep'), 'real hashdeep is not installed')
    def test_real_hashdeep(self):
        (self.root / '真实, document.md').write_text('真实文档', encoding='utf-8')
        actual = changes.snapshot(self.root, {'include': ['**/*.md']})
        self.assertEqual(actual['真实, document.md']['sha256'],
                         hashlib.sha256('真实文档'.encode()).hexdigest())

    @unittest.skipUnless(shutil.which('hashdeep'), 'real hashdeep is not installed')
    def test_real_hashdeep_batch(self):
        names = ['plain.md', '中文, 空格.md', 'a b.md']
        for name in names:
            (self.root / name).write_text(name, encoding='utf-8')
        actual = changes.snapshot(self.root, {'include': ['**/*.md']})
        self.assertEqual(sorted(actual), sorted(names))
        for name in names:
            self.assertEqual(actual[name]['sha256'],
                             hashlib.sha256(name.encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
