"""
Sabu project
jug_sim_buildings package
test_scenario_001_evaluation module
Distinguish measured execution evidence from unexercised failure handling.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from tempfile import TemporaryDirectory
from pathlib import Path
import json
import unittest

from jug_sim_buildings.scenario_001.config import ScenarioConfig
from jug_sim_buildings.scenario_001.run_artifacts import RunArtifacts
from jug_sim_buildings.scenario_001.evaluation import capture_provenance, write_evaluation
from jug_sim_buildings.scenario_001.contracts import load_json


class TestEvaluation(unittest.TestCase):
    def test_operator_provenance_is_preserved_and_resolves_against_config_file(self):
        with TemporaryDirectory() as root:
            root = Path(root)
            manifest = root / 'operator.json'
            data = b'{"lca":{"service_version":"declared-test","cache_hit":"unavailable"}}\n'
            manifest.write_bytes(data)
            config_path = root / 'config.json'
            config_path.write_text(json.dumps({'gis_cities_url': 'http://cities',
                'gis_validation_url': 'http://validation', 'output_root': 'runs', 'fsa': 'H3B',
                'evaluation_provenance_path': 'operator.json'}))
            config = ScenarioConfig.from_file(config_path)
            self.assertEqual(config.evaluation_provenance_path, str(manifest))
            store = RunArtifacts(config.output_root, fsa='H3B')
            capture_provenance(store, config)
            self.assertEqual(store.path('reports/operator_provenance.json').read_bytes(), data)
            self.assertEqual(load_json(store.path('reports/provenance.json'))['upstream']['status'], 'operator_supplied')

    def test_success_does_not_claim_failure_injection_or_remote_provenance(self):
        with TemporaryDirectory() as root:
            store = RunArtifacts(root, fsa='H3B')
            config = ScenarioConfig('http://cities', 'http://validation', root, fsa='H3B')
            capture_provenance(store, config)
            self.assertEqual(load_json(store.path('reports/provenance.json'))['upstream']['status'], 'unavailable')
            state = {'status': 'succeeded', 'fsa': 'H3B', 'lca': {'status': 'succeeded'},
                     'trace': {'status': 'complete'}}
            report = write_evaluation(store, state)
            self.assertEqual(report['criteria']['end_to_end_execution']['status'], 'passed')
            self.assertEqual(report['criteria']['failure_handling']['status'], 'not_exercised')
            state.update(status='failed', error={'stage': 'lca_submission', 'message': 'timeout'})
            report = write_evaluation(store, state)
            self.assertEqual(report['criteria']['end_to_end_execution']['status'], 'failed')
            self.assertEqual(report['criteria']['failure_handling']['status'], 'failure_recorded')
