"""
Sabu project
jug_sim_buildings package
test_scenario_001_end_to_end module
Exercise controlled H3B HTTP execution and stop dependent work on failure.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import requests

from jug_sim_buildings.http_transport import HTTPTransport
from jug_sim_buildings.scenario_001.config import ScenarioConfig
from jug_sim_buildings.scenario_001.contracts import load_json
from jug_sim_buildings.scenario_001.run_artifacts import RunArtifacts, file_digest
from jug_sim_buildings.scenario_001.traceability import json_lines
from jug_sim_buildings.scenario_001.workflow import run_scenario, ScenarioRunError
from test_scenario_001_workflow import workflow_fixture, json_response
from test_scenario_001_preparation import ControlledReprojector
from test_scenario_001_lca_results import result


class Backend(ControlledReprojector):
    def resolve_crs(self, declarations, config):
        return {**super().resolve_crs(declarations, config), 'target_crs': 'EPSG:4326'}


class TestCompleteScenario(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = ScenarioConfig('http://cities/api', 'http://validation', self.root,
                                    fsa='H3B', preparation_enabled=True, lca_enabled=True, lca_url='http://lca')
        self.transport = HTTPTransport()
        self.addCleanup(self.transport.close)
        preprocessing, collection, uniquification = workflow_fixture()
        preprocessing = {key: value.replace('H2M', 'H3B') if isinstance(value, str) else value
                         for key, value in preprocessing.items()}
        for feature in collection['features'] + uniquification['retained_geojson']['features']:
            feature['properties'].update(FSA='H3B', height=10, year_of_construction=1980,
                                         function='1000', address='test')
        collection['features'][-1]['properties']['height'] = None
        uniquification['retained_geojson']['features'][-1]['properties']['height'] = None
        self.payloads = [preprocessing, collection, uniquification,
                         [result(100004), result(100001), result(100003)]]
        self.calls = []

    def execute(self, responses):
        responses = iter(responses)
        def request(method, url, **kwargs):
            self.calls.append({'method': method, 'url': url,
                               'headers': kwargs['headers'],
                               'body': kwargs['data'].read() if kwargs.get('data') else None})
            response = next(responses)
            if isinstance(response, Exception):
                raise response
            return response
        with patch.object(self.transport.session, 'request', side_effect=request), \
                patch('jug_sim_buildings.scenario_001.reprojection.check_capability'), \
                patch('jug_sim_buildings.scenario_001.preparation.CityGISOOReprojector', return_value=Backend()):
            try:
                return run_scenario(self.config, transport=self.transport)
            finally:
                self.directory = next((self.root / 'H3B').iterdir())

    def responses(self):
        return [json_response(value, status) for value, status in zip(self.payloads, [201, 200, 200, 201])]

    def test_complete_http_flow_preserves_bytes_ids_and_all_original_histories(self):
        outcome = self.execute(self.responses())
        self.assertEqual(len(self.calls), 4)
        self.assertTrue(all(c['headers']['X-Request-ID'] == outcome['run_id'] for c in self.calls))
        self.assertEqual(self.calls[-1]['body'], Path(outcome['preparation']['lca_input_path']).read_bytes())
        self.assertEqual(outcome['lca']['summary']['total_reported_lca_scope'], 36.)
        rows = json_lines(self.directory / 'trace/records.jsonl')
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(row['lca'] is not None for row in rows), 3)
        self.assertIsNone(rows[0]['lca'])  # Removed duplicate has no separately attributed carbon.
        self.assertEqual(rows[0]['preparation']['applies_to'], 'retained_representative')
        self.assertEqual(rows[-1]['preparation']['status'], 'rejected')
        state = load_json(self.directory / 'run.json')
        self.assertTrue(all(s['status'] == 'succeeded' for s in state['stage_outcomes']))
        for name, digest in state['artifacts'].items():
            self.assertEqual(file_digest(self.directory / name), digest, name)
        report = load_json(self.directory / 'reports/evaluation.json')
        self.assertEqual(report['criteria']['traceability']['status'], 'passed')

    def test_failures_stop_dependent_requests_and_preserve_primary_error(self):
        for index in range(4):
            with self.subTest(index=index):
                # Each subcase must own a new run root.
                self.calls = []
                responses = self.responses()
                responses[index] = requests.ReadTimeout('injected stage timeout')
                with self.assertRaisesRegex(ScenarioRunError, 'injected stage timeout'):
                    self.execute(responses)
                self.assertEqual(len(self.calls), index + 1)
                state = load_json(self.directory / 'run.json')
                self.assertEqual(state['status'], 'failed')
                self.assertEqual(state['stage_outcomes'][-1]['status'], 'failed')
                self.assertNotIn('lca', state)
                self.assertTrue((self.directory / 'reports/evaluation.json').exists())
                # Keep every run; the next iteration finds its own new root.
                from dataclasses import replace
                self.root = self.root / f'next-{index}'
                self.config = replace(self.config, output_root=self.root)

    def test_identifier_mismatch_is_failure_even_with_equal_counts(self):
        self.payloads[-1][-1]['feature_id'] = 999
        with self.assertRaisesRegex(ScenarioRunError, 'Unresolved LCA result'):
            self.execute(self.responses())
        self.assertEqual(len(self.calls), 4)
        report = load_json(self.directory / 'lca/reconciliation.json')
        self.assertEqual(report['unexpected_ids'], [999])
        self.assertFalse((self.directory / 'lca/summary.json').exists())
        rows = json_lines(self.directory / 'trace/records.jsonl')
        self.assertTrue(any(row['lca'] and row['lca']['status'] == 'unresolved' for row in rows))

    def test_preparation_failure_prevents_lca_and_preserves_rejections(self):
        for feature in self.payloads[1]['features'] + self.payloads[2]['retained_geojson']['features']:
            feature['properties']['height'] = None
        with self.assertRaisesRegex(ScenarioRunError, 'No eligible records'):
            self.execute(self.responses())
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len(list((self.directory / 'preparation').glob('*/rejections.json'))), 1)
        self.assertEqual(load_json(self.directory / 'run.json')['error']['stage'], 'preparation')

    def test_cleanup_error_does_not_hide_lca_failure_or_remove_payload(self):
        responses = self.responses()
        responses[-1] = requests.ReadTimeout('original timeout')
        with patch.object(RunArtifacts, 'cleanup', return_value=[{'message': 'locked scratch'}]):
            with self.assertRaisesRegex(ScenarioRunError, 'original timeout'):
                self.execute(responses)
        state = load_json(self.directory / 'run.json')
        self.assertTrue(state['cleanup_errors'])
        self.assertTrue((self.directory / 'requests/lca.geojson').exists())
        self.assertTrue((self.directory / 'responses/lca.http.json').exists())
