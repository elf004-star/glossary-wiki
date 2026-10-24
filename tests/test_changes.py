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


class ChangesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / '.Glossary-Wiki/state'
        self.state.mkdir(parents=True)
        changes.atomic_json(self.state / 'scope.json', {'include': ['**/*.md'], 'exclude': ['vendor/**']})

    def fake_hashdeep(self, argv, cwd, **kwargs):
        self.assertEqual(argv[1:4], ['-c', 'sha256', '-l'])
        content = (cwd / argv[-1]).read_bytes()
        return subprocess.CompletedProcess(argv, 0,
            f'%%%% HASHDEEP-1.0\n%%%% size,sha256,filename\n{len(content)},{hashlib.sha256(content).hexdigest()},{argv[-1]}\n', '')

    def invoke(self, command, reviewed=False):
        with patch.object(changes.shutil, 'which', return_value='/test/hashdeep'), \
             patch.object(changes.subprocess, 'run', side_effect=self.fake_hashdeep), \
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

    @unittest.skipUnless(shutil.which('hashdeep'), 'real hashdeep is not installed')
    def test_real_hashdeep(self):
        (self.root / '真实, document.md').write_text('真实文档', encoding='utf-8')
        actual = changes.snapshot(self.root, {'include': ['**/*.md']})
        self.assertEqual(actual['真实, document.md']['sha256'],
                         hashlib.sha256('真实文档'.encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
