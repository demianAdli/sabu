"""Exercise real winding-aware geometry reading across application and API calls."""

from contextlib import ExitStack
from copy import deepcopy
from functools import partial
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from marshmallow import ValidationError

from src.jug_lca_buildings.application import EmissionsApplicationService
from src.jug_lca_buildings.schemas.schemas import LCAInputDataSchema
from src.jug_lca_buildings.storage import EmissionsArtifactStore
from tests.geometry_fixtures import clockwise_city, geometry_cities, with_reversed_rings
from tests.test_emissions_api import _build_test_app
from tests.test_input_validation import APPLICATION


WORKFLOW = 'src.jug_lca_buildings.lca_carbon_workflow'


class TestGeometryWindingApi(unittest.TestCase):
    def setUp(self):
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        self.temp_dir = self.context.enter_context(tempfile.TemporaryDirectory())
        self.cache_dir = Path(self.temp_dir) / 'artifacts'
        self.context.enter_context(patch.dict(os.environ, {
            'JUG_LCA_ARTIFACTS_DIR': str(self.cache_dir),
        }))
        # Run the real workflow constructor and geometry reader. Only skip
        # construction enrichment and LCA calculations, which are unrelated.
        self.construction = self.context.enter_context(patch(f'{WORKFLOW}.ConstructionFactory'))
        self.export = self.context.enter_context(patch(
            f'{WORKFLOW}.LCACarbonWorkflow.export_emissions', autospec=True,
            side_effect=self._geometry_results,
        ))
        # Keep the workflow's temporary GeoJSON files inside this test's cleanup.
        temporary_file = partial(tempfile.NamedTemporaryFile, dir=self.temp_dir)
        self.context.enter_context(patch(
            'src.jug_lca_buildings.life_cycle_assessment.input_geojson_content.'
            'tempfile.NamedTemporaryFile', new=temporary_file,
        ))
        self.client = _build_test_app().test_client()

    @staticmethod
    def _geometry_results(workflow):
        return [
            {'component_embodied_emissions': float(building.floor_area),
             'component_end_of_life_emissions': float(building.volume)}
            for building in workflow.city.buildings
        ]

    def _post(self, endpoint, payload):
        if endpoint.startswith('/emissions/upload'):
            return self.client.post(endpoint, data={
                'geojson_file': (io.BytesIO(json.dumps(payload).encode('utf-8')),
                                 'buildings.geojson'),
            })
        return self.client.post(endpoint, json=payload)

    def test_both_endpoints_and_direct_calls_run_real_reader_for_either_winding(self):
        mixed = geometry_cities()[-1][1]
        expected = EmissionsApplicationService.compute_emissions(mixed).emissions_data
        cases = [
            (f'mixed_{exterior}_{holes}', with_reversed_rings(mixed, exterior, holes), expected)
            for exterior in (False, True) for holes in (False, True)
        ]
        regression = clockwise_city()
        polygon = deepcopy(regression)
        geometry = polygon['features'][0]['geometry']
        geometry['type'] = 'Polygon'
        geometry['coordinates'] = geometry['coordinates'][0]
        regression_expected = EmissionsApplicationService.compute_emissions(
            regression).emissions_data
        cases.extend([('reported_multipolygon', regression, regression_expected),
                      ('reported_polygon', polygon, regression_expected)])
        for label, payload, expected_result in cases:
            for entrypoint in ('direct', '/emissions', '/emissions/upload'):
                with self.subTest(label=label, entrypoint=entrypoint), patch.dict(os.environ, {
                    'JUG_LCA_ARTIFACTS_DIR': str(self.cache_dir / label / entrypoint.strip('/')),
                }):
                    original = deepcopy(payload)
                    self.export.reset_mock()
                    if entrypoint == 'direct':
                        result = EmissionsApplicationService.compute_emissions(payload)
                        self.assertFalse(result.cache_hit)
                        self.assertEqual(result.emissions_data, expected_result)
                    else:
                        response = self._post(entrypoint, payload)
                        self.assertEqual(response.status_code, 201)
                        self.assertEqual(response.get_json(), expected_result)
                        csv_response = self._post(f'{entrypoint}?export=csv', payload)
                        self.assertEqual(csv_response.status_code, 200)
                        self.assertEqual(csv_response.mimetype, 'text/csv')
                    self.export.assert_called_once()
                    result = EmissionsApplicationService.compute_emissions(payload)
                    self.assertTrue(result.cache_hit)
                    stored = EmissionsArtifactStore().base_dir / result.request_hash / 'request.json'
                    self.assertEqual(json.loads(stored.read_text(encoding='utf-8')),
                                     LCAInputDataSchema().load(payload))
                    self.assertEqual(payload, original)

    def test_clockwise_input_file_and_json_text_are_preserved(self):
        source = Path(self.temp_dir) / 'clockwise.geojson'
        payload = clockwise_city()
        source.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        original_bytes = source.read_bytes()
        first = EmissionsApplicationService.compute_emissions(str(source))
        self.assertFalse(first.cache_hit)
        self.assertEqual(len(first.emissions_data), 1)
        for source_input in (source.read_text(encoding='utf-8'), payload):
            result = EmissionsApplicationService.compute_emissions(source_input)
            self.assertTrue(result.cache_hit)
            self.assertEqual(result.request_hash, first.request_hash)
        self.export.assert_called_once()
        self.assertEqual(source.read_bytes(), original_bytes)

    def test_old_cache_is_retained_but_not_used_for_winding_corrected_results(self):
        payload = with_reversed_rings(geometry_cities()[0][1], holes=True)
        normalized = LCAInputDataSchema().load(payload)
        store = EmissionsArtifactStore()
        with patch.object(EmissionsArtifactStore, 'CACHE_NAMESPACE',
                          'jug_lca_buildings_emissions_v1'):
            old_hash = store.build_request_hash(normalized)
            store.save_emissions_data(old_hash, normalized, [{'incorrect_old_result': 1}])
            store.save_csv_report(old_hash, 'incorrect old csv')
        old_dir = store.base_dir / old_hash
        old_files = {path.name: path.read_bytes() for path in old_dir.iterdir()}
        result = EmissionsApplicationService.compute_emissions(payload)
        self.assertFalse(result.cache_hit)
        self.assertNotEqual(result.request_hash, old_hash)
        self.assertIn('component_embodied_emissions', result.emissions_data[0])
        report = EmissionsApplicationService.build_csv_report(payload, result)
        self.assertFalse(report['cache_hit'])
        self.assertNotEqual(report['csv_text'], 'incorrect old csv')
        self.assertEqual({path.name: path.read_bytes() for path in old_dir.iterdir()}, old_files)
        self.assertTrue(EmissionsApplicationService.compute_emissions(payload).cache_hit)
        self.export.assert_called_once()

    def test_invalid_clockwise_batch_still_rejected_before_reader_and_cache(self):
        payload = clockwise_city()
        invalid = deepcopy(payload['features'][0])
        invalid['id'] = 100001
        invalid['properties']['height'] = None
        payload['features'].append(invalid)
        with patch(f'{APPLICATION}.EmissionsArtifactStore') as store:
            with self.assertRaises(ValidationError) as caught:
                EmissionsApplicationService.compute_emissions(payload)
            expected = json.loads(json.dumps(caught.exception.messages))
            for endpoint in ('/emissions', '/emissions/upload'):
                response = self._post(endpoint, payload)
                self.assertEqual(response.status_code, 422)
                errors = response.get_json()['errors']
                self.assertEqual(errors.get('json', errors), expected)
            store.assert_not_called()
        self.construction.assert_not_called()
        self.export.assert_not_called()
