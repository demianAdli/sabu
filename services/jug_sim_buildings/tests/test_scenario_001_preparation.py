"""
Sabu project
jug_sim_buildings package
test_scenario_001_preparation module
Verify normalization, lineage, preparation reconciliation and failures.
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

from jug_sim_buildings.scenario_001.config import ScenarioConfig
from jug_sim_buildings.scenario_001.contracts import load_json
from jug_sim_buildings.scenario_001.lca_contract import normalize_feature
from jug_sim_buildings.scenario_001.preparation import prepare_run, PreparationError
from jug_sim_buildings.scenario_001.reporting import source_record
from jug_sim_buildings.scenario_001.run_artifacts import RunArtifacts, file_digest


def feature(identifier=10):
    return {'type': 'Feature', 'id': identifier, 'geometry': {
        'type': 'Polygon', 'coordinates': [[[-73.6, 45.5], [-73.599, 45.5],
                                            [-73.599, 45.501], [-73.6, 45.5]]]},
        'properties': {'height': '10.5', 'year_of_construction': '1980', 'function': '1000',
                       'address': 'Example', 'citygisoo_area': 123.456,
                       'roll_provincial_id': str(identifier), 'source_extra': {'mixed': [1, '001']}}}


def saved_run(root, values=None):
    values = values if values is not None else [feature(), feature(11)]
    originals = deepcopy(values)
    for f in originals:
        f['properties']['citygisoo_id'] = f'source-{f["id"]}'
    retained = deepcopy(originals)
    for f in retained:
        f.pop('id')
    records = [{'record_ref': f'record:{i}', 'input_position': i,
                'identifier': f['properties']['roll_provincial_id'],
                'area': f['properties']['citygisoo_area'], 'status': 'retained',
                'retained_record_ref': f'record:{i}', 'retained_feature_index': i,
                'reason': 'unique_identifier'} for i, f in enumerate(originals)]
    store = RunArtifacts(root, fsa='H3B')
    crs = {'type': 'name', 'properties': {'name': 'EPSG:4326'}}
    payloads = {
        'input/standardized.geojson': {'type': 'FeatureCollection', 'features': originals, 'crs': crs},
        'retained.geojson': {'type': 'FeatureCollection', 'features': retained},
        'records.json': records,
        'source_crs.json': {'source': 'input/standardized.geojson', 'declaration': crs},
        'statistics.json': {'applied': True, 'unique_attribute_key': 'roll_provincial_id',
                            'ranking_area_key': 'citygisoo_area', 'input_features': len(values),
                            'retained_features': len(values), 'removed_features': 0, 'duplicate_groups': 0},
    }
    digests = {}
    for name, payload in payloads.items():
        digests[name] = file_digest(store.write_json(name, payload))
    store.write_json_lines('source_records.jsonl', [source_record(store.run_id, i, f)
                                                  for i, f in enumerate(originals)])
    digests['source_records.jsonl'] = file_digest(store.path('source_records.jsonl'))
    store.write_json('run.json', {'scenario': 'scenario_001', 'run_id': store.run_id,
                                 'fsa': 'H3B', 'status': 'succeeded', 'artifacts': digests})
    return store


class ControlledReprojector:
    def resolve_crs(self, declarations, config):
        if not any(v is not None for _, v in declarations):
            raise ValueError('Source CRS missing.')
        return {'source_crs': 'EPSG:4326', 'target_crs': 'EPSG:4326',
                'status': 'copied', 'warnings': [], 'capability': {'controlled': True}}

    def geometry_error(self, geometry):
        return None

    def transform(self, features, report, destination, scratch_dir, coordinate_operation=None):
        Path(destination).write_text(json.dumps({'type': 'FeatureCollection', 'features': features}))


class TestPreparation(unittest.TestCase):
    def test_normalization_collects_offending_fields_without_inventing_values(self):
        source = feature()
        source['properties']['name'] = 'name'
        normalized, errors, changes = normalize_feature(source)
        self.assertEqual(errors, [])
        self.assertEqual(normalized['properties']['height'], 10.5)
        self.assertEqual(normalized['properties']['year_of_construction'], 1980)
        self.assertEqual(source['properties']['height'], '10.5')
        for bad in (None, '', True, 'not a year', 1980.5, '1980.5', 0):
            candidate = deepcopy(source)
            candidate['properties']['year_of_construction'] = bad
            self.assertTrue(normalize_feature(candidate)[1], bad)
        candidate = deepcopy(source)
        candidate['properties'].update(height=None, function=None, address=None)
        self.assertEqual(len(normalize_feature(candidate)[1]), 3)
        candidate['geometry']['coordinates'][0].pop()
        self.assertIn('geometry', [e['field'] for e in normalize_feature(candidate)[1]])

    def test_reconciliation_source_preservation_repeat_attempts_and_mapping(self):
        with TemporaryDirectory() as directory:
            bad = feature(11)
            bad['properties']['height'] = None
            store = saved_run(directory, [feature(), bad])
            snapshots = {p: p.read_bytes() for p in store.directory.rglob('*') if p.is_file()}
            config = ScenarioConfig('http://cities', 'http://validation', directory, fsa='H3B')
            first = prepare_run(store.directory, config, reprojector=ControlledReprojector())
            second = prepare_run(store.directory, config, reprojector=ControlledReprojector())
            self.assertNotEqual(first['attempt_id'], second['attempt_id'])
            self.assertEqual(first['counts']['retained_input'], 2)
            self.assertEqual(first['counts']['accepted'], 1)
            self.assertEqual(first['counts']['rejected'], 1)
            for path, data in snapshots.items():
                self.assertEqual(path.read_bytes(), data)
            attempt = Path(first['preparation_directory'])
            final = load_json(Path(first['lca_input_path']))
            self.assertEqual(final['features'][0]['id'], 10)
            self.assertEqual(final['features'][0]['properties']['source_extra'], {'mixed': [1, '001']})
            self.assertNotIn('crs', final)
            self.assertEqual(list((attempt / 'tmp').iterdir()), [])
            mappings = [json.loads(line) for line in (attempt / 'id_mappings.jsonl').read_text().splitlines()]
            self.assertEqual([m['status'] for m in mappings], ['accepted', 'rejected'])
            self.assertEqual(mappings[0]['input_records'][0]['source']['feature_id'], 10)

    def test_zero_eligible_and_export_failures_preserve_evidence(self):
        for export_failure in (False, True):
            with self.subTest(export_failure=export_failure), TemporaryDirectory() as directory:
                source = feature()
                if not export_failure:
                    source['properties']['height'] = None
                store = saved_run(directory, [source])
                config = ScenarioConfig('http://cities', 'http://validation', directory, fsa='H3B')
                backend = ControlledReprojector()
                if export_failure:
                    def fail(*args, **kwargs):
                        Path(args[2]).write_text('partial')
                        raise RuntimeError('export failed')
                    backend.transform = fail
                with self.assertRaises(PreparationError) as caught:
                    prepare_run(store.directory, config, reprojector=backend)
                attempt = caught.exception.directory
                self.assertFalse((attempt / 'lca_input.geojson').exists())
                self.assertTrue((attempt / 'rejections.json').exists())
                self.assertEqual(load_json(attempt / 'preparation.json')['status'], 'failed')
                if export_failure:
                    self.assertEqual((attempt / 'evidence/lca-final.geojson.partial').read_text(), 'partial')

    def test_hash_mismatch_and_failed_run_stop_before_reprojection(self):
        with TemporaryDirectory() as directory:
            store = saved_run(directory)
            store.path('retained.geojson').write_text('{}')
            backend = ControlledReprojector()
            with patch.object(backend, 'resolve_crs') as resolve:
                with self.assertRaisesRegex(PreparationError, 'hash mismatch'):
                    prepare_run(store.directory, ScenarioConfig('http://c', 'http://v', directory, fsa='H3B'),
                                reprojector=backend)
            resolve.assert_not_called()

    def test_rehashed_bad_mapping_still_fails_lineage_validation(self):
        with TemporaryDirectory() as directory:
            store = saved_run(directory)
            records = load_json(store.path('records.json'))
            records[0]['input_position'] = 1
            store.write_json('records.json', records)
            state = load_json(store.path('run.json'))
            state['artifacts']['records.json'] = file_digest(store.path('records.json'))
            store.write_json('run.json', state)
            with self.assertRaisesRegex(PreparationError, 'input-position'):
                prepare_run(store.directory, ScenarioConfig('http://c','http://v', directory, fsa='H3B'),
                            reprojector=ControlledReprojector())

    def test_preparation_only_failure_can_be_retried_without_changing_parent(self):
        with TemporaryDirectory() as directory:
            store = saved_run(directory)
            state = load_json(store.path('run.json'))
            state.update(status='failed', error={'stage': 'preparation', 'message': 'export failed'})
            store.write_json('run.json', state)
            before = store.path('run.json').read_bytes()
            result = prepare_run(store.directory, ScenarioConfig('http://c','http://v',directory,fsa='H3B'),
                                 reprojector=ControlledReprojector())
            self.assertEqual(result['status'], 'succeeded')
            self.assertEqual(store.path('run.json').read_bytes(), before)

    def test_cleanup_error_never_replaces_original_export_error(self):
        from jug_sim_buildings.scenario_001.run_artifacts import PreparationArtifacts
        with TemporaryDirectory() as directory:
            store = saved_run(directory)
            backend = ControlledReprojector()
            with patch.object(backend, 'transform', side_effect=RuntimeError('original export failure')), \
                    patch.object(PreparationArtifacts, 'cleanup', return_value=[{'message': 'scratch locked'}]):
                with self.assertRaisesRegex(PreparationError, 'original export failure') as caught:
                    prepare_run(store.directory, ScenarioConfig('http://c','http://v',directory,fsa='H3B'),
                                reprojector=backend)
            metadata = load_json(caught.exception.directory / 'preparation.json')
            self.assertEqual(metadata['cleanup_errors'], [{'message': 'scratch locked'}])
