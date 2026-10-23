"""
Sabu project
jug_sim_buildings package
test_reader_exclusions module
Check evidenced reader exclusions, opt-in API behavior and isolated caches.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.jug_lca_buildings.application import EmissionsApplicationService
from src.jug_lca_buildings.lca_carbon_workflow import LCACarbonWorkflow
from src.jug_lca_buildings.life_cycle_assessment.geojson_geometry import BuildingGeometryFactory
from src.jug_lca_buildings.storage import EmissionsArtifactStore


WORKFLOW = 'src.jug_lca_buildings.application.jug_lca_buildings.LCACarbonWorkflow'


def rectangle(x=-73.6, y=45.5, width=.001):
    return [[x, y], [x + width, y], [x + width, y + width], [x, y + width], [x, y]]


def feature(identifier, geometry):
    return {'type': 'Feature', 'id': identifier, 'properties': {
        'name': f'H3B_{identifier}', 'address': 'test', 'function': '1000',
        'height': 10, 'year_of_construction': 1980}, 'geometry': geometry}


def exclusion(identifier, area=1.):
    return {'feature_id': identifier, 'reason_code': 'reader_floor_area_below_minimum',
            'field': 'geometry', 'reason': 'Reader floor area below its 25 m2 minimum.',
            'reader_floor_area_m2': area, 'minimum_floor_area_m2': 25.}


def result(identifier):
    return {'feature_id': identifier, 'opening_embodied_emissions': 1.,
            'envelope_embodied_emissions': 2., 'component_embodied_emissions': 3.,
            'opening_end_of_life_emissions': 4., 'envelope_end_of_life_emissions': 5.,
            'component_end_of_life_emissions': 9.}


class TestReaderExclusions(unittest.TestCase):
    def test_calculation_uses_actual_building_identity_even_if_collection_reorders(self):
        class ReorderedCity:
            reads = 0

            @property
            def buildings(self):
                self.reads += 1
                names = ('1', '2') if self.reads == 1 else ('2', '1')
                return [SimpleNamespace(name=name) for name in names]

        workflow = object.__new__(LCACarbonWorkflow)
        workflow.city = ReorderedCity()
        workflow.submitted_feature_ids = {'1': 1, '2': 2}
        workflow.include_exclusions = True
        workflow.exclusions = []
        workflow.progress_log_every = 100
        workflow.calculate_building_component_emission = lambda b: tuple(int(b.name) * value for value in (2, 1, 3, 5, 4, 9))
        for key in ('envelope_emission', 'opening_emission', 'component_emission',
                    'envelope_end_of_life_emission', 'opening_end_of_life_emission', 'component_end_of_life_emission'):
            setattr(workflow, 'building_' + key, [])
        for row in workflow.export_emissions():
            self.assertEqual(row['component_embodied_emissions'], row['feature_id'] * 3)

    def test_actual_reader_uses_combined_parts_holes_and_preserves_source(self):
        city = {'type': 'FeatureCollection', 'features': [
            feature(1, {'type': 'Polygon', 'coordinates': [rectangle()]}),
            feature(2, {'type': 'Polygon', 'coordinates': [rectangle(width=.00001)]}),
            feature(3, {'type': 'MultiPolygon', 'coordinates': [[rectangle(x=-73.59 + i * .0001, width=.00003)] for i in range(4)]}),
            feature(4, {'type': 'Polygon', 'coordinates': [rectangle(x=-73.58, width=.0001),
                     rectangle(x=-73.579999, y=45.500001, width=.000098)]})]}
        with TemporaryDirectory() as root:
            path = Path(root) / 'H3B.geojson'
            path.write_text(json.dumps(city), encoding='utf-8')
            before = path.read_bytes()
            factory = BuildingGeometryFactory('geojson', path=path, height_field='height',
                year_of_construction_field='year_of_construction', function_field='function')
            parsed = factory.city
            self.assertEqual({b.name for b in parsed.buildings}, {'1', '3'})
            self.assertEqual({row['reader_name'] for row in factory.reader_exclusions}, {'2', '4'})
            self.assertTrue(all(0 <= row['reader_floor_area_m2'] < 25 for row in factory.reader_exclusions))
            self.assertEqual(path.read_bytes(), before)

    def test_opt_in_calculates_remaining_buildings_and_strict_mode_still_fails(self):
        city = {'type': 'FeatureCollection', 'features': [
            feature(1, {'type': 'Polygon', 'coordinates': [rectangle()]}),
            feature(2, {'type': 'Polygon', 'coordinates': [rectangle(width=.00001)]})]}
        with TemporaryDirectory() as root:
            path = Path(root) / 'H3B.geojson'
            path.write_text(json.dumps(city), encoding='utf-8')
            with patch('src.jug_lca_buildings.lca_carbon_workflow.ConstructionFactory') as construction, \
                    patch.object(LCACarbonWorkflow, 'calculate_building_component_emission', return_value=(2, 1, 3, 5, 4, 9)) as calculation:
                workflow = LCACarbonWorkflow(str(path), 'nrcan_archetypes.json', 'nrcan_constructions_cap_3.json', include_exclusions=True)
                self.assertEqual([row['feature_id'] for row in workflow.export_emissions()], [1])
                self.assertEqual([row['feature_id'] for row in workflow.exclusions], [2])
                self.assertLess(workflow.exclusions[0]['reader_floor_area_m2'], 25)
                self.assertEqual(calculation.call_count, 1)
                construction.assert_called_once()
            with self.assertRaisesRegex(ValueError, 'reader identity mismatch'):
                LCACarbonWorkflow(str(path), 'nrcan_archetypes.json', 'nrcan_constructions_cap_3.json')

    def test_all_excluded_skips_enrichment_and_returns_empty_results(self):
        city = {'type': 'FeatureCollection', 'features': [
            feature(2, {'type': 'Polygon', 'coordinates': [rectangle(width=.00001)]})]}
        with TemporaryDirectory() as root:
            path = Path(root) / 'H3B.geojson'
            path.write_text(json.dumps(city), encoding='utf-8')
            with patch('src.jug_lca_buildings.lca_carbon_workflow.ConstructionFactory') as construction:
                workflow = LCACarbonWorkflow(str(path), 'nrcan_archetypes.json', 'nrcan_constructions_cap_3.json', include_exclusions=True)
                self.assertEqual(workflow.export_emissions(), [])
                self.assertEqual(workflow.exclusions[0]['feature_id'], 2)
                construction.assert_not_called()

    def test_unknown_missing_duplicate_or_overlapping_identity_still_fails(self):
        for exclusions, names in (([], ['1']), ([exclusion(2, 25)], ['1']),
                                  ([exclusion(2), exclusion(2)], ['1']),
                                  ([exclusion(2)], ['1', '2']), ([exclusion(9)], ['1'])):
            workflow = object.__new__(LCACarbonWorkflow)
            workflow.submitted_feature_ids = {'1': 1, '2': 2}
            workflow.include_exclusions = True
            workflow.exclusions = exclusions
            workflow.city = SimpleNamespace(buildings=[SimpleNamespace(name=name) for name in names])
            with self.subTest(exclusions=exclusions, names=names), self.assertRaises(ValueError):
                workflow._reader_feature_ids()


class TestExclusionAPIAndCache(unittest.TestCase):
    def setUp(self):
        from tests.test_emissions_api import TestEmissionsApi
        fixture = TestEmissionsApi()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        self.client = fixture.client
        self.payload = deepcopy(fixture.valid_payload)
        second = deepcopy(self.payload['features'][0])
        second['id'] = 2
        self.payload['features'].append(second)
        self.fixture = fixture

    def test_opt_in_json_upload_and_warm_cache_preserve_outcomes_and_ids(self):
        original = deepcopy(self.payload)
        with patch(WORKFLOW) as workflow:
            workflow.return_value.export_emissions.return_value = [result(2)]
            workflow.return_value.exclusions = [exclusion(1)]
            response = self.client.post('/emissions?include_exclusions=true', json=self.payload)
            self.assertEqual(response.status_code, 201)
            expected = response.get_json()
            self.assertEqual(expected['counts'], {'submitted': 2, 'calculated': 1, 'excluded': 1})
            uploaded = self.client.post('/emissions/upload?include_exclusions=true', data={
                'geojson_file': (io.BytesIO(json.dumps(self.payload).encode()), 'H3B.geojson')})
            self.assertEqual(uploaded.status_code, 201)
            self.assertEqual(uploaded.get_json(), expected)
            self.assertEqual(workflow.call_count, 1)
            self.assertTrue(workflow.call_args.kwargs['include_exclusions'])
        self.assertEqual(self.payload, original)

    def test_opt_in_cache_isolated_from_legacy_and_corrupt_partition_not_reused(self):
        store = EmissionsArtifactStore()
        from src.jug_lca_buildings.application.input_validation import normalize_city_input
        normalized = normalize_city_input(self.payload)
        strict_hash = store.build_request_hash(normalized)
        opt_hash = store.build_request_hash(normalized, include_exclusions=True)
        self.assertNotEqual(strict_hash, opt_hash)
        store.save_emissions_data(strict_hash, normalized, [result(1), result(2)])
        strict_before = (store.base_dir / strict_hash / 'emissions.json').read_bytes()
        with patch(WORKFLOW) as workflow:
            workflow.return_value.export_emissions.return_value = [result(2)]
            workflow.return_value.exclusions = [exclusion(1)]
            EmissionsApplicationService.compute_emissions(self.payload, include_exclusions=True)
            self.assertEqual(workflow.call_count, 1)
        path = store.base_dir / opt_hash / 'reader_outcome.json'
        corrupted = json.loads(path.read_text())
        corrupted['exclusions'] = []
        path.write_text(json.dumps(corrupted), encoding='utf-8')
        with patch(WORKFLOW) as workflow, self.assertRaisesRegex(ValueError, 'missing reader outcome'):
            EmissionsApplicationService.compute_emissions(self.payload, include_exclusions=True)
        workflow.assert_not_called()
        self.assertEqual((store.base_dir / strict_hash / 'emissions.json').read_bytes(), strict_before)

    def test_invalid_query_or_csv_combination_does_not_compute(self):
        with patch(WORKFLOW) as workflow:
            for suffix in ('?include_exclusions=yes', '?include_exclusions=true&export=csv'):
                self.assertEqual(self.client.post('/emissions' + suffix, json=self.payload).status_code, 400)
            workflow.assert_not_called()

    def test_generated_openapi_exposes_opt_in_on_both_endpoints(self):
        api = self.fixture.app.extensions['flask-smorest']['apis']['']['ext_obj']
        paths = api.spec.to_dict()['paths']
        for endpoint in ('/emissions', '/emissions/upload'):
            parameter = next(p for p in paths[endpoint]['post']['parameters'] if p['name'] == 'include_exclusions')
            self.assertEqual(parameter['schema'], {'type': 'boolean', 'default': False})

    def test_direct_csv_report_rejects_partial_outcomes_instead_of_positional_join(self):
        with patch(WORKFLOW) as workflow:
            workflow.return_value.export_emissions.return_value = [result(2)]
            workflow.return_value.exclusions = [exclusion(1)]
            completed = EmissionsApplicationService.compute_emissions(self.payload, include_exclusions=True)
            with self.assertRaisesRegex(ValueError, 'CSV reporting'):
                EmissionsApplicationService.build_csv_report(self.payload, completed)

    def test_legacy_response_stays_array_and_all_excluded_opt_in_is_explicit(self):
        with patch(WORKFLOW) as workflow:
            workflow.return_value.export_emissions.return_value = [result(1), result(2)]
            response = self.client.post('/emissions', json=self.payload)
            self.assertIsInstance(response.get_json(), list)
            self.assertEqual(workflow.call_args.kwargs, {})
            workflow.return_value.export_emissions.return_value = []
            workflow.return_value.exclusions = [exclusion(1), exclusion(2)]
            response = self.client.post('/emissions?include_exclusions=true', json=self.payload)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.get_json()['counts'], {'submitted': 2, 'calculated': 0, 'excluded': 2})
