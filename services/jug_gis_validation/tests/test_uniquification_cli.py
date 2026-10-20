import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from test_uniquification_application import (
    REPO_ROOT, SERVICE_ROOT, SKIP_REASON, buildings_payload, no_validation_processing, run_standalone,
)

if SKIP_REASON is None:
    from jug_gis_validation import __main__ as cli


@unittest.skipIf(SKIP_REASON, SKIP_REASON)
class TestUniquificationCLI(unittest.TestCase):
    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(cli, 'configure_service_logging'), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_stdout_and_file_results_equal_shared_operation(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.geojson'
            output = Path(folder) / 'nested' / 'result.json'
            source.write_text(json.dumps(buildings_payload()), encoding='utf-8')
            original = source.read_bytes()
            args = ['uniquify', '--buildings-set', str(source),
                    '--unique-attribute-key', 'roll_id', '--area-key', 'rank_area']
            with no_validation_processing():
                code, stdout, stderr = self.invoke(args)
                self.assertEqual(code, 0, stderr)
                self.assertEqual(stderr, '')
                self.assertEqual(json.loads(stdout), run_standalone(source).as_dict())
                code, stdout, stderr = self.invoke(args + ['--output-path', str(output)])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, '')
            self.assertEqual(json.loads(output.read_text()), run_standalone(source).as_dict())
            self.assertEqual(source.read_bytes(), original)

    def test_rejects_input_overwrite_and_hard_link_alias(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.geojson'
            source.write_text(json.dumps(buildings_payload()), encoding='utf-8')
            alias = Path(folder) / 'alias.json'
            os.link(source, alias)
            original = source.read_bytes()
            for output in (source, alias):
                code, stdout, stderr = self.invoke([
                    'uniquify', '--buildings-set', str(source),
                    '--unique-attribute-key', 'roll_id', '--output-path', str(output)])
                self.assertEqual(code, 1)
                self.assertEqual(stdout, '')
                self.assertIn('must not overwrite', stderr)
                self.assertEqual(source.read_bytes(), original)

    def test_processing_error_has_stderr_and_no_json(self):
        code, stdout, stderr = self.invoke([
            'uniquify', '--buildings-set', 'missing.geojson',
            '--unique-attribute-key', 'roll_id'])
        self.assertEqual(code, 1)
        self.assertEqual(stdout, '')
        self.assertIn('path does not exist', stderr)

    def test_argument_errors_exit_two(self):
        for args in (['uniquify'], ['uniquify', '--buildings-set', 'in.geojson',
                                   '--unique-attribute-key', 'id', '--plot']):
            with self.subTest(args=args), self.assertRaises(SystemExit) as caught:
                self.invoke(args)
            self.assertEqual(caught.exception.code, 2)

    def test_module_invocation_emits_parseable_json(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.geojson'
            source.write_text(json.dumps(buildings_payload()), encoding='utf-8')
            environment = dict(os.environ, PYTHONPATH=os.pathsep.join([
                str(SERVICE_ROOT / 'src'), str(REPO_ROOT / 'libs/sabu_chassis/src')]),
                LOG_DIR_BASE=folder, LOG_LEVEL='CRITICAL', MPLBACKEND='Agg')
            completed = subprocess.run([
                sys.executable, '-m', 'jug_gis_validation', 'uniquify',
                '--buildings-set', str(source), '--unique-attribute-key', 'roll_id',
                '--area-key', 'rank_area'], env=environment, capture_output=True,
                text=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), run_standalone(source).as_dict())


if __name__ == '__main__':
    unittest.main()
