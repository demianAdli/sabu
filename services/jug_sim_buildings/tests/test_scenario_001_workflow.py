"""
Sabu project
jug_sim_buildings package
test_scenario_001_workflow module
Verify ordered scenario calls with controlled HTTP responses.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import requests
from sabu_chassis.logging.context import get_request_id, set_request_id

from jug_sim_buildings.http_transport import HTTPTransport
from jug_sim_buildings.scenario_001.config import ScenarioConfig
from jug_sim_buildings.scenario_001.contracts import ContractError, load_json
from jug_sim_buildings.scenario_001.reporting import duplicate_report
from jug_sim_buildings.scenario_001.run_artifacts import RunArtifacts
from jug_sim_buildings.scenario_001.workflow import ScenarioRunError, run_scenario
from test_http_transport import ControlledResponse


def workflow_fixture():
    """Synthetic polygons: a tied ID group, missing/blank IDs, and an invalid singleton area."""
    collection = {'type': 'FeatureCollection',
                  'crs': {'type': 'name', 'properties': {'name': 'EPSG:32188'}}, 'features': []}
    identifiers = ['0001', '0001', '0001', None, '  ', 123]
    areas = [10, '20', 20, None, -4, 'not numeric']
    for position, (identifier, area) in enumerate(zip(identifiers, areas)):
        collection['features'].append({
            'type': 'Feature', 'id': 100000 + position,
            'geometry': {'type': 'Polygon', 'coordinates': [
                [[0, 0], [1, 0], [1, 1], [0, 0]]]},
            'properties': {'roll_provincial_id': identifier, 'citygisoo_area': area,
                           'citygisoo_id': f'source-{position}', 'usage_provincial_id': f'u-{position}',
                           'processing_tool': 'fixture', 'processed_by': 'test', 'FSA': 'H2M'},
        })
    retained_positions = [1, 3, 4, 5]
    retained_features = [deepcopy(collection['features'][i]) for i in retained_positions]
    for feature in retained_features:
        feature.pop('id')  # Actual upstream export deliberately drops top-level IDs.
    records = []
    for position, (identifier, area) in enumerate(zip(identifiers, areas)):
        winner = 1 if position < 3 else position
        records.append({
            'record_ref': f'record:{position}', 'input_position': position,
            'identifier': identifier, 'area': area,
            'status': 'retained' if position in retained_positions else 'removed',
            'retained_record_ref': f'record:{winner}',
            'retained_feature_index': retained_positions.index(winner),
            'reason': ['smaller_area', 'earliest_maximum_area', 'later_tied_maximum',
                       'missing_identifier', 'missing_identifier', 'unique_identifier'][position],
        })
    result = {
        'uniquification': {'applied': True, 'unique_attribute_key': 'roll_provincial_id',
                          'ranking_area_key': 'citygisoo_area', 'input_features': 6,
                          'retained_features': 4, 'removed_features': 2, 'duplicate_groups': 1},
        'retained_geojson': {'type': 'FeatureCollection', 'features': retained_features},
        'records': records,
    }
    preprocessing = {
        'component_name': 'mtl_fsa_gisoo', 'mode': 'standardize', 'fsa': 'H2M',
        'workflow_output_path': '/upstream/H2M/raw.gpkg',
        'standardized_output_path': '/upstream/H2M/standardized.geojson',
        'cleaned_output_paths': ['/upstream/H2M/usage_clean'],
        'standardized_artifact_id': 'a' * 32,
        'standardized_download_url': f'http://cities/api/artifacts/{"a" * 32}/download',
    }
    return preprocessing, collection, result


def json_response(value, status=200):
    return ControlledResponse(json.dumps(value, ensure_ascii=False).encode('utf-8'), status)


class TestScenarioWorkflow(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = ScenarioConfig('http://cities/api', 'http://validation', self.root,
                                     keep_outputs=['inter_summary'])
        self.transport = HTTPTransport()
        self.addCleanup(self.transport.close)
        previous_id = get_request_id()
        self.addCleanup(set_request_id, previous_id)
        set_request_id('caller-context')
        self.calls = []

    def execute(self, responses, *, config=None):
        responses = iter(responses)

        def request(method, url, **kwargs):
            body = kwargs['data'].read() if kwargs.get('data') is not None else None
            self.calls.append({'method': method, 'url': url, 'body': body,
                               'request_context': get_request_id(), **kwargs})
            response = next(responses)
            if isinstance(response, Exception):
                raise response
            return response

        with patch.object(self.transport.session, 'request', side_effect=request):
            try:
                return run_scenario(config or self.config, transport=self.transport)
            finally:
                self.assertEqual(get_request_id(), 'caller-context')

    def last_run(self):
        directories = list(self.root.iterdir())
        self.assertEqual(len(directories), 1)
        return directories[0]

    def test_success_preserves_exact_input_ids_mappings_crs_and_correlated_requests(self):
        preprocessing, collection, result = workflow_fixture()
        original_input = json.dumps(collection, indent=3).encode()
        outcome = self.execute([json_response(preprocessing, 201),
                                ControlledResponse(original_input), json_response(result)])
        directory = Path(outcome['run_directory'])
        self.assertEqual(outcome['status'], 'succeeded')
        self.assertEqual([c['method'] for c in self.calls], ['POST', 'GET', 'POST'])
        self.assertEqual([c['url'] for c in self.calls], [
            'http://cities/api/components/mtl_fsa_gisoo/runs',
            preprocessing['standardized_download_url'], 'http://validation/uniquifications'])
        self.assertEqual(json.loads(self.calls[0]['body']), self.config.preprocessing_request())
        self.assertEqual(json.loads(self.calls[2]['body']), {
            'buildings_set': collection, 'unique_attribute_key': 'roll_provincial_id',
            'area_key': 'citygisoo_area'})
        for call, operation in zip(self.calls, ('preprocess', 'download', 'uniquification')):
            self.assertEqual(call['headers']['X-Request-ID'], outcome['run_id'])
            self.assertEqual(call['request_context'], outcome['run_id'])
            self.assertEqual(call['timeout'], self.config.timeout(operation))
        self.assertEqual((directory / 'input/standardized.geojson').read_bytes(), original_input)
        self.assertEqual(load_json(directory / 'retained.geojson'), result['retained_geojson'])
        self.assertEqual(load_json(directory / 'records.json'), result['records'])
        self.assertEqual(load_json(directory / 'statistics.json'), result['uniquification'])
        sources = [json.loads(line) for line in (directory / 'source_records.jsonl').read_text().splitlines()]
        for position, source in enumerate(sources):
            self.assertEqual(source['input_position'], position)
            self.assertEqual(source['feature_id'], collection['features'][position]['id'])
            self.assertEqual(source['source_identifiers']['citygisoo_id'], f'source-{position}')
            self.assertEqual(source['run_id'], outcome['run_id'])
        self.assertEqual(load_json(directory / 'source_crs.json')['declaration'], collection['crs'])
        metadata = load_json(directory / 'run.json')
        self.assertEqual(metadata['counts']['removed_features'], 2)
        self.assertEqual(metadata['cleanup_errors'], [])
        self.assertEqual(metadata['artifacts']['input/standardized.geojson']['sha256'],
                         hashlib.sha256(original_input).hexdigest())
        self.assertEqual(list((directory / 'tmp').iterdir()), [])
        report = load_json(directory / 'reports/duplicates.json')
        self.assertEqual(report['sampled_groups'][0]['winner_record_ref'], 'record:1')
        self.assertEqual(report['sampled_groups'][0]['policy_check'], 'passed')
        self.assertIn('Whole-run removed: 2', (directory / 'reports/summary.md').read_text())

    def test_debug_configuration_and_absent_crs_are_preserved(self):
        preprocessing, collection, result = workflow_fixture()
        collection.pop('crs')
        config = ScenarioConfig('http://cities/api', 'http://validation', self.root,
                                cleanup_outputs=False)
        self.execute([json_response(preprocessing, 201), json_response(collection), json_response(result)],
                     config=config)
        self.assertEqual(json.loads(self.calls[0]['body'])['cleanup_outputs'], False)
        self.assertEqual(json.loads(self.calls[0]['body'])['keep_outputs'], [])
        crs = load_json(self.last_run() / 'source_crs.json')
        self.assertEqual(crs['status'], 'unknown')
        self.assertIsNone(crs['declaration'])
        self.assertFalse(crs['coordinates_transformed'])

    def test_source_trace_handles_duplicated_and_missing_top_level_ids(self):
        preprocessing, collection, result = workflow_fixture()
        collection['features'][1]['id'] = collection['features'][0]['id']
        collection['features'][2].pop('id')
        self.execute([json_response(preprocessing, 201), json_response(collection), json_response(result)])
        sources = [json.loads(line) for line in (
            self.last_run() / 'source_records.jsonl').read_text().splitlines()]
        self.assertEqual(sources[0]['feature_id'], sources[1]['feature_id'])
        self.assertNotEqual(sources[0]['record_ref'], sources[1]['record_ref'])
        self.assertFalse(sources[2]['feature_id_present'])
        self.assertIsNone(sources[2]['feature_id'])
        self.assertEqual(sources[0]['source_identifiers']['roll_provincial_id'], '0001')

    def test_required_input_persistence_failure_prevents_uniquification(self):
        preprocessing, collection, _ = workflow_fixture()
        with patch.object(RunArtifacts, 'write_json_lines', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(ScenarioRunError, 'disk full') as caught:
                self.execute([json_response(preprocessing, 201), json_response(collection)])
        self.assertEqual(len(self.calls), 2)
        self.assertTrue((caught.exception.directory / 'input/standardized.geojson').exists())
        self.assertEqual(load_json(caught.exception.directory / 'run.json')['status'], 'failed')

    def test_preprocessing_failures_stop_download_and_keep_response(self):
        preprocessing, _, _ = workflow_fixture()
        cases = [json_response({'message': 'cleanup failed after artifact registration'}, 500),
                 requests.Timeout('ambiguous preprocessing completion'),
                 ControlledResponse(b'not json', 201)]
        for change in ({'fsa': 'H3H'}, {'mode': 'independent'}, {'component_name': 'wrong'},
                       {'standardized_artifact_id': None}, {'standardized_download_url': None},
                       {'standardized_download_url': 'http://other/artifacts/id/download'},
                       {'standardized_download_url': 'http://cities/api/not-an-artifact'},
                       {'cleaned_output_paths': None}):
            cases.append(json_response(preprocessing | change, 201))
        for response in cases:
            with self.subTest(response=response), TemporaryDirectory() as directory:
                config = ScenarioConfig('http://cities/api', 'http://validation', Path(directory))
                self.calls = []
                with self.assertRaises(ScenarioRunError) as caught:
                    self.execute([response], config=config)
                self.assertEqual(len(self.calls), 1)
                run = caught.exception.directory
                self.assertTrue((run / 'responses/preprocessing.body').exists())
                metadata = load_json(run / 'run.json')
                self.assertEqual(metadata['status'], 'failed')
                self.assertEqual(list((run / 'tmp').iterdir()), [])

    def test_download_failures_stop_uniquification_and_preserve_partial_evidence(self):
        preprocessing, _, _ = workflow_fixture()
        for response in (ControlledResponse(b'gone', 410),
                         ControlledResponse(b'full', chunks=[b'pa', requests.ConnectionError('lost')])):
            with self.subTest(response=response), TemporaryDirectory() as directory:
                config = ScenarioConfig('http://cities/api', 'http://validation', Path(directory))
                self.calls = []
                with self.assertRaises(ScenarioRunError) as caught:
                    self.execute([json_response(preprocessing, 201), response], config=config)
                self.assertEqual(len(self.calls), 2)
                run = caught.exception.directory
                self.assertTrue((run / 'evidence/standardized.partial').exists())
                self.assertFalse((run / 'input/standardized.geojson').exists())
                self.assertTrue((run / 'responses/preprocessing.body').exists())
                self.assertEqual(list((run / 'tmp').iterdir()), [])

    def test_invalid_downloaded_contract_is_preserved_without_uniquification(self):
        preprocessing, collection, _ = workflow_fixture()
        missing_column = deepcopy(collection)
        for feature in missing_column['features']:
            feature['properties'].pop('citygisoo_area')
        for body in (b'invalid geojson', json.dumps(missing_column).encode(),
                     b'{"type":"FeatureCollection","features":[]}'):
            with self.subTest(body=body), TemporaryDirectory() as directory:
                self.calls = []
                config = ScenarioConfig('http://cities/api', 'http://validation', Path(directory))
                with self.assertRaises(ScenarioRunError) as caught:
                    self.execute([json_response(preprocessing, 201), ControlledResponse(body)], config=config)
                self.assertEqual(len(self.calls), 2)
                self.assertEqual((caught.exception.directory / 'input/standardized.geojson').read_bytes(), body)

    def test_uniquification_contract_and_reconciliation_failures_preserve_raw_result(self):
        preprocessing, collection, result = workflow_fixture()
        mutations = [
            lambda r: r.pop('records'),
            lambda r: r['uniquification'].update(input_features=99),
            lambda r: r['uniquification'].update(removed_features=99),
            lambda r: r['uniquification'].update(duplicate_groups=2),
            lambda r: r['uniquification'].update(ranking_area_key='roll_area'),
            lambda r: r['retained_geojson']['features'].pop(),
            lambda r: r['records'][0].update(input_position=1),
            lambda r: r['records'][0].update(retained_record_ref='record:0'),
            lambda r: r['records'][0].update(retained_feature_index=9),
            lambda r: r['records'][1].update(retained_record_ref='record:2'),
            lambda r: r['records'][0].update(identifier='different'),
            lambda r: r['records'][0].update(area=999),
            lambda r: r['records'][2].update(status='retained', retained_record_ref='record:2'),
            lambda r: r['retained_geojson']['features'][0]['properties'].update(citygisoo_id='changed'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), TemporaryDirectory() as directory:
                broken = deepcopy(result)
                mutation(broken)
                self.calls = []
                config = ScenarioConfig('http://cities/api', 'http://validation', Path(directory))
                with self.assertRaises(ScenarioRunError) as caught:
                    self.execute([json_response(preprocessing, 201), json_response(collection),
                                  json_response(broken)], config=config)
                self.assertEqual(len(self.calls), 3)
                run = caught.exception.directory
                self.assertEqual(load_json(run / 'responses/uniquification.body'), broken)
                self.assertFalse((run / 'retained.geojson').exists())
                self.assertTrue((run / 'source_records.jsonl').exists())
                self.assertEqual(list((run / 'tmp').iterdir()), [])

    def test_uniquification_http_failure_and_cleanup_error_keep_primary_error(self):
        preprocessing, collection, _ = workflow_fixture()
        with patch.object(RunArtifacts, 'cleanup', return_value=[{'message': 'scratch locked'}]):
            with self.assertRaisesRegex(ScenarioRunError, 'HTTP 422') as caught:
                self.execute([json_response(preprocessing, 201), json_response(collection),
                              json_response({'message': 'invalid duplicate area'}, 422)])
        metadata = load_json(caught.exception.directory / 'run.json')
        self.assertEqual(metadata['cleanup_errors'], [{'message': 'scratch locked'}])
        self.assertIn('HTTP 422', metadata['error']['message'])
        self.assertTrue((caught.exception.directory / 'input/standardized.geojson').exists())

    def test_success_with_cleanup_error_preserves_completed_outputs(self):
        preprocessing, collection, result = workflow_fixture()
        with patch.object(RunArtifacts, 'cleanup', return_value=[{'message': 'scratch locked'}]):
            outcome = self.execute([json_response(preprocessing, 201), json_response(collection),
                                    json_response(result)])
        self.assertEqual(outcome['status'], 'succeeded_with_cleanup_errors')
        self.assertTrue((Path(outcome['run_directory']) / 'retained.geojson').exists())

    def test_finalization_failure_retains_primary_http_error_and_fallback_metadata(self):
        original = RunArtifacts.write_json

        def write_json(artifacts, relative, value):
            if relative == 'run.json' and 'finished_at' in value:
                raise PermissionError('run metadata locked')
            return original(artifacts, relative, value)

        with patch.object(RunArtifacts, 'write_json', write_json):
            with self.assertRaisesRegex(ScenarioRunError, 'HTTP 500') as caught:
                self.execute([json_response({'message': 'preprocessing failed'}, 500)])
        fallback = load_json(caught.exception.directory / 'evidence/finalization.json')
        self.assertIn('HTTP 500', fallback['error']['message'])
        self.assertEqual(fallback['metadata_error'], 'run metadata locked')

    def test_sample_is_bounded_and_checks_earliest_tied_maximum(self):
        _, collection, result = workflow_fixture()
        report = duplicate_report(result['records'], collection['features'])
        self.assertEqual(report['sampled_groups'][0]['maximum_area'], 20)
        broken = deepcopy(result['records'])
        for record in broken[:3]:
            record['retained_record_ref'] = 'record:2'
        with self.assertRaises(ContractError):
            duplicate_report(broken, collection['features'])
        records, inputs = [], []
        for group in range(5):
            for member in range(15):
                position = len(records)
                records.append({'record_ref': f'record:{position}', 'input_position': position,
                                'retained_record_ref': f'record:{group * 15}', 'identifier': str(group),
                                'status': 'retained' if member == 0 else 'removed', 'area': 10})
                inputs.append(collection['features'][0])
        report = duplicate_report(records, inputs)
        self.assertEqual(report['whole_run_duplicate_groups'], 5)
        self.assertEqual(len(report['sampled_groups']), 3)
        self.assertEqual([g['omitted_members'] for g in report['sampled_groups']], [5, 5, 5])

    def test_json_duplicate_keys_and_nonfinite_constants_are_contract_errors(self):
        path = self.root / 'invalid.json'
        for text in ('{"features": [], "features": [1]}', '{"area": NaN}'):
            path.write_text(text)
            with self.assertRaises(ContractError):
                load_json(path)
