"""
Sabu project
jug_sim_buildings package
test_scenario_001_lca_submission module
Exercise exact LCA submissions and durable failure evidence.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import requests

from jug_sim_buildings.http_transport import HTTPTransport, TransportError
from jug_sim_buildings.scenario_001.config import ScenarioConfig
from jug_sim_buildings.scenario_001.contracts import ContractError, load_json
from jug_sim_buildings.scenario_001.lca_submission import submit_prepared
from jug_sim_buildings.scenario_001.preparation import prepare_run
from test_http_transport import ControlledResponse
from test_scenario_001_lca_results import result, exclusion, outcome
from test_scenario_001_preparation import saved_run, feature, ControlledReprojector


class TestLCASubmission(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.config = ScenarioConfig('http://cities', 'http://validation', temp.name, fsa='H3B',
                                    preparation_enabled=True, lca_enabled=True, lca_url='http://lca/prefix',
                                    lca_connect_timeout_seconds=4, lca_read_timeout_seconds=99)
        self.store = saved_run(temp.name)
        self.prepared = prepare_run(self.store.directory, self.config, reprojector=ControlledReprojector())
        self.transport = HTTPTransport()
        self.addCleanup(self.transport.close)
        self.stages = []

    def submit(self, response):
        def request(method, url, **kwargs):
            self.assertEqual(url, 'http://lca/prefix/emissions?include_exclusions=true')
            self.assertEqual(kwargs['data'].read(), Path(self.prepared['lca_input_path']).read_bytes())
            self.assertEqual(kwargs['headers']['X-Request-ID'], self.store.run_id)
            self.assertEqual(kwargs['timeout'], (4, 99))
            if isinstance(response, Exception):
                raise response
            return response
        with patch.object(self.transport.session, 'request', side_effect=request) as call:
            try:
                return submit_prepared(self.store, self.prepared, self.config, self.transport, self.stages.append)
            finally:
                self.calls = call.call_count

    def test_exact_bytes_and_reordered_results(self):
        response = ControlledResponse(json.dumps(outcome([result(11), result(10)])).encode(), 201)
        completed = self.submit(response)
        self.assertEqual(completed['submitted'], 2)
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.stages, ['lca_submission', 'lca_contract'])
        self.assertEqual(self.store.path('requests/lca.geojson').read_bytes(),
                         Path(self.prepared['lca_input_path']).read_bytes())
        self.assertTrue(self.store.path('lca/results.json').exists())

    def test_http_timeout_and_invalid_response_preserve_evidence(self):
        with self.assertRaises(TransportError):
            self.submit(requests.ReadTimeout('controlled timeout'))
        self.assertEqual(self.calls, 1)
        self.assertTrue(self.store.path('responses/lca.http.json').exists())
        self.assertFalse(self.store.path('lca/results.json').exists())

    def test_response_ids_must_account_for_all_inputs(self):
        with self.assertRaises(ContractError):
            self.submit(ControlledResponse(json.dumps(outcome([result(10)])).encode(), 201))
        report = load_json(self.store.path('lca/reconciliation.json'))
        self.assertEqual(report['missing_ids'], [11])
        self.assertTrue(self.store.path('responses/lca.body').exists())
        self.assertFalse(self.store.path('lca/summary.json').exists())

    def test_valid_exclusions_are_preserved_without_changing_submitted_bytes(self):
        completed = self.submit(ControlledResponse(json.dumps(outcome([result(11)], [exclusion(10)])).encode(), 201))
        self.assertEqual((completed['calculated'], completed['excluded']), (1, 1))
        self.assertEqual(load_json(self.store.path('lca/exclusions.json'))[0]['feature_id'], 10)
        self.assertEqual(completed['summary']['buildings'], 1)

    def test_all_excluded_preserves_decisions_but_does_not_publish_zero_carbon(self):
        with self.assertRaisesRegex(ContractError, 'All submitted records were excluded'):
            self.submit(ControlledResponse(json.dumps(outcome([], [exclusion(10), exclusion(11)])).encode(), 201))
        self.assertEqual(len(load_json(self.store.path('lca/exclusions.json'))), 2)
        self.assertEqual(load_json(self.store.path('lca/reconciliation.json'))['status'], 'succeeded')
        self.assertFalse(self.store.path('lca/summary.json').exists())

    def test_tampered_preparation_prevents_http(self):
        Path(self.prepared['lca_input_path']).write_text('{}')
        with self.assertRaises(ContractError), patch.object(self.transport.session, 'request') as call:
            submit_prepared(self.store, self.prepared, self.config, self.transport, self.stages.append)
        call.assert_not_called()

    def test_http_error_preserves_original_error_response(self):
        with self.assertRaises(TransportError):
            self.submit(ControlledResponse(b'{"message":"reader identity mismatch"}', 500))
        self.assertEqual(self.calls, 1)
        self.assertIn('reader identity mismatch', self.store.path('responses/lca.body').read_text())
        self.assertEqual(load_json(self.store.path('responses/lca.http.json'))['status'], 500)
        self.assertFalse(self.store.path('lca/results.json').exists())

    def test_malformed_response_does_not_publish_results(self):
        with self.assertRaises(ContractError):
            self.submit(ControlledResponse(b'{"truncated":', 201))
        self.assertFalse(self.store.path('lca/results.json').exists())
        self.assertEqual(self.store.path('responses/lca.body').read_bytes(), b'{"truncated":')

    def test_interrupted_response_preserves_partial_bytes_without_retry(self):
        response = ControlledResponse(b'ignored', 201,
            chunks=[b'[{"feature_id":10}', requests.exceptions.ChunkedEncodingError('disconnect')])
        with self.assertRaises(TransportError):
            self.submit(response)
        self.assertEqual(self.calls, 1)
        self.assertEqual(self.store.path('responses/lca.body').read_bytes(), b'[{"feature_id":10}')
        self.assertFalse(load_json(self.store.path('responses/lca.http.json'))['complete'])

    def test_submission_configuration_validation(self):
        for changes in ({'preparation_enabled': False}, {'lca_url': None},
                        {'lca_connect_timeout_seconds': 0}, {'lca_enabled': 'yes'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.config, **changes)
