# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from paths import data_home
from migrate import migrate
from session_manager import Sessions


class PortableStateTests(unittest.TestCase):
    def test_explicit_home_is_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {'CONTEXT_BRIDGE_HOME': tmp}):
                self.assertEqual(data_home(), Path(tmp))

    def test_relative_override_is_rejected(self):
        with patch.dict(os.environ, {'CONTEXT_BRIDGE_HOME': 'relative-state'}):
            with self.assertRaises(ValueError):
                data_home()

    def test_macos_uses_application_support(self):
        with patch.dict(os.environ, {}, clear=True), patch('paths.platform.system', return_value='Darwin'), patch('paths.Path.home', return_value=Path('/test-user')):
            self.assertEqual(data_home(), Path('/test-user/Library/Application Support/ContextBridge'))

    def test_migration_preserves_approvals_original_and_database(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'old', Path(tmp) / 'new'
            manager = Sessions(source)
            sid = manager.create('Research')
            manager.approve(sid, False)
            original = json.loads(manager.config.read_text())
            db = sqlite3.connect(original['database'])
            db.execute('CREATE TABLE marker (value TEXT)')
            db.execute('INSERT INTO marker VALUES (?)', ('original',))
            db.commit(); db.close()
            migrate(source, target)
            result = json.loads(Sessions(target).config.read_text())
            self.assertEqual(result['sessions'], original['sessions'])
            self.assertEqual(result['approved_transcripts'], original['approved_transcripts'])
            self.assertEqual(json.loads(manager.config.read_text()), original)
            db = sqlite3.connect(result['database'])
            self.assertEqual(db.execute('SELECT value FROM marker').fetchone()[0], 'original')
            db.close()
            with self.assertRaises(ValueError):
                migrate(source, target)
