"""
Sabu project
jug_sim_buildings package
test_scenario_001_config module
Verify scenario configuration and CLI boundaries.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from jug_sim_buildings.scenario_001.config import ScenarioConfig
from jug_sim_buildings.scenario_001.__main__ import main


class TestScenarioConfig(unittest.TestCase):
    def config(self, **overrides):
        values = dict(gis_cities_url='http://cities/api/',
                      gis_validation_url='http://validation/', output_root='output_files/runs')
        return ScenarioConfig(**(values | overrides))

    def test_defaults_and_cleanup_forwarding(self):
        config = self.config()
        self.assertEqual(config.preprocessing_request(), {
            'mode': 'standardize', 'fsa': 'H2M', 'cleanup_outputs': True, 'keep_outputs': []})
        self.assertEqual(config.gis_cities_url, 'http://cities/api')
        self.assertEqual(config.timeout('preprocess'), (10, 7200))
        self.assertEqual(self.config(cleanup_outputs=False).preprocessing_request()['cleanup_outputs'], False)
        config = self.config(keep_outputs=[' usage_clean ', 'inter_summary', 'usage_clean'], fsa=' h2m ')
        self.assertEqual(config.preprocessing_request()['keep_outputs'], ['usage_clean', 'inter_summary'])
        self.assertEqual(config.fsa, 'H2M')

    def test_invalid_configuration_is_rejected_before_network_or_output(self):
        cases = [
            {'cleanup_outputs': False, 'keep_outputs': ['usage_clean']},
            {'cleanup_outputs': 'false'}, {'keep_outputs': 'usage_clean'},
            {'keep_outputs': ['']}, {'keep_outputs': [3]}, {'fsa': '../H2M'},
            {'fsa': 123}, {'output_root': ''},
        ]
        for key in ('connect_timeout_seconds', 'preprocess_read_timeout_seconds',
                    'download_read_timeout_seconds', 'uniquification_read_timeout_seconds'):
            cases.extend({key: value} for value in (0, -1, float('nan'), float('inf'), True, '10'))
        for value in ('file:///tmp/data', 'http://user:pass@cities', 'http://cities?x=1',
                      'http://cities/#fragment', 'http://cities:bad', 'http://ci ties', 'http://cities\\bad'):
            cases.append({'gis_cities_url': value})
        for case in cases:
            with self.subTest(case=case), self.assertRaises((ValueError, TypeError)):
                self.config(**case)

    def test_file_paths_resolve_against_configuration_location_and_unknown_keys_fail(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'scenario.json'
            values = {'gis_cities_url': 'http://cities', 'gis_validation_url': 'http://validation',
                      'output_root': 'runs'}
            path.write_text(json.dumps(values))
            self.assertEqual(ScenarioConfig.from_file(path).output_root, Path(directory) / 'runs')
            self.assertFalse((Path(directory) / 'runs').exists())
            values['typo'] = True
            path.write_text(json.dumps(values))
            with self.assertRaises(TypeError):
                ScenarioConfig.from_file(path)

    def test_cli_help_and_invalid_config_have_no_logging_or_network_side_effects(self):
        with TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.pop('PYTHONPATH', None)
            for args, status in ((['--help'], 0), (['--config', 'missing.json'], 2)):
                result = subprocess.run(
                    [sys.executable, '-B', '-m', 'jug_sim_buildings.scenario_001', *args],
                    cwd=directory, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_cli_prints_run_result_and_nonzero_processing_failure(self):
        config = self.config()
        with patch.object(ScenarioConfig, 'from_file', return_value=config), \
                patch('jug_sim_buildings.logging_setup.configure_service_logging'), \
                patch('jug_sim_buildings.scenario_001.workflow.run_scenario') as run:
            run.return_value = {'run_id': 'a' * 32, 'status': 'succeeded'}
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(['--config', 'config.json']), 0)
            self.assertEqual(json.loads(stdout.getvalue()), run.return_value)
            run.assert_called_once_with(config)
            run.side_effect = RuntimeError('failure evidence in run directory')
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(main(['--config', 'config.json']), 1)
            self.assertIn('failure evidence', stderr.getvalue())
