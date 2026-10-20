"""Polygon/MultiPolygon validation across application and HTTP boundaries."""

from contextlib import ExitStack
from copy import deepcopy
import csv
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
from tests.geometry_fixtures import (
    add_metadata_and_numeric_strings, geometry_cities, invalid_geometries,
)
from tests.test_emissions_api import _build_test_app
from tests.test_input_validation import APPLICATION, valid_city


class TestGeometryValidation(unittest.TestCase):
    def setUp(self):
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        self.temp_dir = self.context.enter_context(tempfile.TemporaryDirectory())
        self.context.enter_context(patch.dict(
            os.environ, {'JUG_LCA_ARTIFACTS_DIR': self.temp_dir}))
        self.workflow = self.context.enter_context(patch(
            f'{APPLICATION}.LCACarbonWorkflow'))
        self.workflow.return_value.export_emissions.return_value = [
            {'component_embodied_emissions': 3.0}]
        self.app = _build_test_app()
        self.client = self.app.test_client()

    def post_city(self, endpoint, city):
        if endpoint.startswith('/emissions/upload'):
            return self.client.post(endpoint, data={
                'geojson_file': (io.BytesIO(json.dumps(city).encode('utf-8')),
                                 'buildings.geojson')})
        return self.client.post(endpoint, data=json.dumps(city),
                                content_type='application/json')

    def test_both_geometry_types_preserve_structure_and_exclude_metadata(self):
        for label, city in geometry_cities():
            with self.subTest(label=label):
                decorated = add_metadata_and_numeric_strings(city)
                original = deepcopy(decorated)
                normalized = LCAInputDataSchema().load(decorated)
                self.assertEqual(normalized, city)
                # Even the deepest coordinate lists must be independent copies.
                normalized['features'][0]['geometry']['coordinates'].clear()
                self.assertEqual(decorated, original)

    def test_no_new_ring_length_or_topology_rules(self):
        for geometry_type, coordinates in (
            ('Polygon', []), ('MultiPolygon', []),
            ('Polygon', [[[1, 2, 3]]]), ('MultiPolygon', [[[[1, 2, 3]]]]),
        ):
            city = valid_city()
            city['features'][0]['geometry'] = {
                'type': geometry_type, 'coordinates': coordinates}
            with self.subTest(geometry_type=geometry_type, coordinates=coordinates):
                self.assertEqual(LCAInputDataSchema().load(city), city)

    def test_geometry_type_keeps_existing_string_normalization(self):
        for label, city in geometry_cities():
            with self.subTest(label=label):
                original = deepcopy(city)
                for feature in city['features']:
                    feature['geometry']['type'] = feature['geometry']['type'].encode()
                self.assertEqual(LCAInputDataSchema().load(city), original)

    def test_invalid_geometry_rejects_mixed_batch_before_cache_lookup(self):
        for geometry in invalid_geometries():
            with self.subTest(geometry=geometry):
                city = deepcopy(geometry_cities()[-1][1])
                city['features'][1]['geometry'] = geometry
                serialized_before = json.dumps(city)
                with patch(f'{APPLICATION}.EmissionsArtifactStore') as store:
                    with self.assertRaises(ValidationError) as caught:
                        EmissionsApplicationService.compute_emissions(city)
                    self.assertIn('geometry', caught.exception.messages['features'][1])
                    expected = json.loads(json.dumps(caught.exception.messages))
                    for endpoint in ('/emissions', '/emissions/upload'):
                        response = self.post_city(endpoint, city)
                        self.assertEqual(response.status_code, 422)
                        errors = response.get_json()['errors']
                        self.assertEqual(errors.get('json', errors), expected)
                    # Paths and JSON text use the same validation too.
                    path = Path(self.temp_dir) / 'invalid.geojson'
                    path.write_text(serialized_before, encoding='utf-8')
                    for source in (serialized_before, str(path)):
                        with self.assertRaises(ValidationError):
                            EmissionsApplicationService.compute_emissions(source)
                    self.assertEqual(path.read_text(encoding='utf-8'), serialized_before)
                    store.assert_not_called()
                self.assertEqual(json.dumps(city), serialized_before)
        self.workflow.assert_not_called()

    def test_supported_inputs_and_endpoints_share_normalized_geometry_cache(self):
        for label, city in geometry_cities():
            with self.subTest(label=label):
                self.workflow.reset_mock()
                decorated = add_metadata_and_numeric_strings(city)
                original = deepcopy(decorated)
                path = Path(self.temp_dir) / f'{label}.geojson'
                path.write_text(json.dumps(decorated, indent=2), encoding='utf-8')
                original_bytes = path.read_bytes()
                first = EmissionsApplicationService.compute_emissions(decorated)
                self.assertFalse(first.cache_hit)
                for source in (city, json.dumps(decorated), str(path)):
                    result = EmissionsApplicationService.compute_emissions(source)
                    self.assertTrue(result.cache_hit)
                    self.assertEqual(result.request_hash, first.request_hash)
                for endpoint in ('/emissions', '/emissions/upload'):
                    self.assertEqual(self.post_city(endpoint, decorated).status_code, 201)
                self.workflow.assert_called_once_with(
                    city, 'nrcan_archetypes.json', 'nrcan_constructions_cap_3.json')
                artifact = Path(self.temp_dir) / first.request_hash / 'request.json'
                self.assertEqual(json.loads(artifact.read_text(encoding='utf-8')), city)
                self.assertEqual(decorated, original)
                self.assertEqual(path.read_bytes(), original_bytes)

    def test_api_cache_misses_and_csv_keep_mixed_feature_ids_and_order(self):
        city = geometry_cities()[-1][1]
        decorated = add_metadata_and_numeric_strings(city)
        results = [{'component_embodied_emissions': 3.0},
                   {'component_embodied_emissions': 7.0}]
        self.workflow.return_value.export_emissions.return_value = results
        for index, endpoint in enumerate(('/emissions', '/emissions/upload')):
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {
                'JUG_LCA_ARTIFACTS_DIR': str(Path(self.temp_dir) / str(index))
            }):
                self.workflow.reset_mock()
                response = self.post_city(endpoint, decorated)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.get_json(), results)
                self.workflow.assert_called_once_with(
                    city, 'nrcan_archetypes.json', 'nrcan_constructions_cap_3.json')
                csv_response = self.post_city(f'{endpoint}?export=csv', decorated)
                self.assertEqual(csv_response.status_code, 200)
                rows = list(csv.DictReader(io.StringIO(csv_response.get_data(as_text=True))))
                self.assertEqual([row['feature_id'] for row in rows], ['1', '2', 'TOTAL'])
                self.assertEqual([float(row['component_embodied_emissions_kgco2e'])
                                  for row in rows], [3.0, 7.0, 10.0])
                self.workflow.assert_called_once()

    def test_generated_openapi_describes_both_native_geometry_layouts(self):
        api = self.app.extensions['flask-smorest']['apis']['']['ext_obj']
        geometry = api.spec.to_dict()['components']['schemas']['Feature'][
            'properties']['geometry']
        alternatives = geometry['oneOf']
        self.assertEqual(len(alternatives), 2)
        for alternative, expected_type, depth in zip(
            alternatives, ('Polygon', 'MultiPolygon'), (3, 4)
        ):
            self.assertEqual(alternative['properties']['type']['enum'], [expected_type])
            coordinates = alternative['properties']['coordinates']
            for _ in range(depth):
                self.assertEqual(coordinates['type'], 'array')
                coordinates = coordinates['items']
            self.assertEqual(coordinates['type'], 'number')
            self.assertTrue(alternative['additionalProperties'])
