"""Shared schema and application/API validation without running LCA."""

from copy import deepcopy
from contextlib import ExitStack
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
from tests.test_emissions_api import _build_test_app


APPLICATION = 'src.jug_lca_buildings.application.jug_lca_buildings'


def valid_city():
    return {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'id': 1,
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[-73.57, 45.5], [-73.56, 45.5],
                                 [-73.56, 45.51], [-73.57, 45.5]]],
            },
            'properties': {
                'name': 'Building 1',
                'address': '123 Test St',
                'function': 'Residential',
                'height': 12.5,
                'year_of_construction': 1995,
            },
        }],
    }


def city_with_metadata():
    city = valid_city()
    city['crs'] = {'type': 'name', 'properties': {'name': 'EPSG:4326'}}
    feature = city['features'][0]
    feature['bbox'] = [-74, 45, -73, 46]
    feature['geometry']['source'] = {'provider': 'survey'}
    feature['properties']['unrelated'] = None
    # Existing Marshmallow coercion must apply to direct callers too.
    feature['id'] = '1'
    feature['geometry']['coordinates'][0][0][0] = '-73.57'
    feature['properties']['height'] = '12.5'
    feature['properties']['year_of_construction'] = '1995'
    return city


def schema_objects(city):
    feature = city['features'][0]
    return [city, feature, feature['geometry'], feature['properties']]


def invalid_cities():
    """Exercise every required field at each schema level."""
    fields_by_level = [
        {'type': 42, 'features': {}},
        {'type': 42, 'id': 'bad', 'geometry': [], 'properties': []},
        {'type': 42, 'coordinates': 'bad'},
        {'name': 42, 'address': 42, 'function': 42,
         'height': 'bad', 'year_of_construction': 'bad'},
    ]
    for level, fields in enumerate(fields_by_level):
        for field, bad_type in fields.items():
            for violation in ('missing', 'null', 'type'):
                city = valid_city()
                obj = schema_objects(city)[level]
                if violation == 'missing':
                    del obj[field]
                else:
                    obj[field] = None if violation == 'null' else bad_type
                yield f'{level}.{field}.{violation}', city
    for value in (None, 'bad', [None], [[None]], [[['bad']]]):
        city = valid_city()
        city['features'][0]['geometry']['coordinates'] = value
        yield f'coordinates.{value!r}', city
    for value in (None, 42):
        city = valid_city()
        city['features'] = [value]
        yield f'feature.{value!r}', city
    yield 'document.null', None
    yield 'document.array', []


class TestGeoJSONSchema(unittest.TestCase):
    def test_unknown_fields_excluded_at_all_levels_without_mutation(self):
        city = city_with_metadata()
        original = deepcopy(city)
        normalized = LCAInputDataSchema().load(city)
        self.assertEqual(normalized, valid_city())
        self.assertEqual(city, original)
        normalized['features'][0]['geometry']['coordinates'][0][0][0] = 0
        self.assertEqual(city, original)

    def test_declared_fields_remain_required_nonnull_and_typed(self):
        for label, city in invalid_cities():
            with self.subTest(label=label):
                with self.assertRaises(ValidationError) as caught:
                    LCAInputDataSchema().load(city)
                self.assertTrue(caught.exception.messages)

    def test_no_extra_domain_rules_or_defaults(self):
        city = valid_city()
        city['type'] = 'custom collection label'
        feature = city['features'][0]
        feature['type'] = 'custom feature label'
        feature['geometry'] = {'type': 'Polygon',
                               'coordinates': [[[1, 2, 3]]]}
        feature['properties']['height'] = -1
        feature['properties']['name'] = ''
        self.assertEqual(LCAInputDataSchema().load(city), city)
        self.assertEqual(LCAInputDataSchema().load(
            {'type': 'FeatureCollection', 'features': []}),
            {'type': 'FeatureCollection', 'features': []})


class TestSharedInputValidation(unittest.TestCase):
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
        self.client = _build_test_app().test_client()

    def post_city(self, endpoint, city):
        if endpoint.startswith('/emissions/upload'):
            return self.client.post(endpoint, data={
                'geojson_file': (io.BytesIO(json.dumps(city).encode('utf-8')),
                                 'buildings.geojson')})
        return self.client.post(endpoint, data=json.dumps(city),
                                content_type='application/json')

    def test_direct_and_api_validation_equivalent_before_cache_access(self):
        with patch(f'{APPLICATION}.EmissionsArtifactStore') as store:
            for label, city in invalid_cities():
                original = deepcopy(city)
                with self.subTest(label=label):
                    with self.assertRaises(ValidationError) as caught:
                        EmissionsApplicationService.compute_emissions(city)
                    # JSON serialization converts numeric feature indexes to strings.
                    expected = json.loads(json.dumps(caught.exception.messages))
                    for endpoint in ('/emissions', '/emissions/upload'):
                        with self.subTest(endpoint=endpoint):
                            response = self.post_city(endpoint, city)
                            self.assertEqual(response.status_code, 422)
                            errors = response.get_json()['errors']
                            self.assertEqual(errors.get('json', errors), expected)
                    self.assertEqual(city, original)
            store.assert_not_called()
        self.workflow.assert_not_called()

    def test_one_invalid_feature_rejects_entire_batch_with_field_details(self):
        city = valid_city()
        invalid = deepcopy(city['features'][0])
        del invalid['properties']['height']
        city['features'].append(invalid)
        original = deepcopy(city)
        with patch(f'{APPLICATION}.EmissionsArtifactStore') as store:
            with self.assertRaises(ValidationError) as caught:
                EmissionsApplicationService.compute_emissions(city)
            details = caught.exception.messages['features'][1]['properties']
            self.assertIn('height', details)
            for endpoint in ('/emissions', '/emissions/upload'):
                response = self.post_city(endpoint, city)
                self.assertEqual(response.status_code, 422)
                errors = response.get_json()['errors']
                self.assertIn('height', errors.get('json', errors)[
                    'features']['1']['properties'])
            store.assert_not_called()
        self.workflow.assert_not_called()
        self.assertEqual(city, original)

    def test_supported_forms_metadata_and_api_share_normalized_cache(self):
        city = city_with_metadata()
        original = deepcopy(city)
        source = Path(self.temp_dir) / 'buildings.geojson'
        source.write_text(json.dumps(city, indent=2), encoding='utf-8')
        original_bytes = source.read_bytes()
        first = EmissionsApplicationService.compute_emissions(city)
        self.assertFalse(first.cache_hit)
        inputs = [valid_city(), json.dumps(city), f'  {source}  ',
                  os.path.relpath(source)]
        for request_city in inputs:
            with self.subTest(input_form=type(request_city).__name__):
                result = EmissionsApplicationService.compute_emissions(request_city)
                self.assertTrue(result.cache_hit)
                self.assertEqual(result.request_hash, first.request_hash)
        for endpoint in ('/emissions', '/emissions/upload'):
            self.assertEqual(self.post_city(endpoint, city).status_code, 201)
        self.workflow.assert_called_once_with(
            valid_city(), 'nrcan_archetypes.json',
            'nrcan_constructions_cap_3.json')
        stored_request = Path(self.temp_dir) / first.request_hash / 'request.json'
        self.assertEqual(json.loads(stored_request.read_text()), valid_city())
        self.assertEqual(city, original)
        self.assertEqual(source.read_bytes(), original_bytes)

    def test_relative_path_package_data_fallback(self):
        package = Path(self.temp_dir)
        data = package / 'data'
        data.mkdir()
        filename = f'{package.name}.geojson'
        source = data / filename
        source.write_text(json.dumps(city_with_metadata()), encoding='utf-8')
        with patch('src.jug_lca_buildings.application.input_validation.__file__',
                   str(package / 'application' / 'input_validation.py')):
            EmissionsApplicationService.compute_emissions(filename)
        self.assertEqual(self.workflow.call_args.args[0], valid_city())

    def test_api_cache_misses_compute_and_report_from_normalized_input(self):
        for endpoint in ('/emissions?export=csv', '/emissions/upload?export=csv'):
            with self.subTest(endpoint=endpoint):
                city = city_with_metadata()
                # Keep each endpoint's request distinct so both start with a miss.
                city['features'][0]['properties']['name'] = endpoint
                expected = valid_city()
                expected['features'][0]['properties']['name'] = endpoint
                original = deepcopy(city)
                self.workflow.reset_mock()
                with patch(f'{APPLICATION}.EmissionsReportExporter.build_csv_text',
                           return_value='normalized csv') as exporter:
                    response = self.post_city(endpoint, city)
                    self.assertEqual(response.status_code, 200)
                    self.workflow.assert_called_once_with(
                        expected, 'nrcan_archetypes.json',
                        'nrcan_constructions_cap_3.json')
                    exporter.assert_called_once_with(
                        expected,
                        self.workflow.return_value.export_emissions.return_value)
                self.assertEqual(city, original)

    def test_invalid_json_text_and_files_fail_before_cache(self):
        source = Path(self.temp_dir) / 'invalid.geojson'
        source.write_bytes(b'{invalid')
        invalid = valid_city()
        del invalid['features'][0]['properties']['name']
        schema_source = Path(self.temp_dir) / 'missing_name.geojson'
        schema_source.write_text(json.dumps(invalid), encoding='utf-8')
        original_bytes = schema_source.read_bytes()
        with patch(f'{APPLICATION}.EmissionsArtifactStore') as store:
            for request_city in ('{invalid', str(source), json.dumps(invalid),
                                 str(schema_source)):
                with self.subTest(request_city=request_city):
                    with self.assertRaises(ValidationError) as caught:
                        EmissionsApplicationService.compute_emissions(request_city)
                    self.assertTrue(caught.exception.messages)
            store.assert_not_called()
        self.assertEqual(source.read_bytes(), b'{invalid')
        self.assertEqual(schema_source.read_bytes(), original_bytes)
        self.workflow.assert_not_called()

    def test_application_validation_errors_return_422_from_both_endpoints(self):
        # In particular, errors raised inside the workflow wrapper must not be 500s.
        details = {'features': {0: {'properties': {'height': ['Invalid value.']}}}}
        with patch(f'{APPLICATION}.EmissionsApplicationService.compute_emissions',
                   side_effect=ValidationError(details)):
            for endpoint in ('/emissions', '/emissions/upload'):
                response = self.post_city(endpoint, valid_city())
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.get_json()['errors'],
                                 json.loads(json.dumps(details)))

    def test_reporting_uses_normalized_input_for_direct_and_api_calls(self):
        city = city_with_metadata()
        original = deepcopy(city)
        source = Path(self.temp_dir) / 'buildings.geojson'
        source.write_text(json.dumps(city), encoding='utf-8')
        original_bytes = source.read_bytes()
        result = EmissionsApplicationService.compute_emissions(city)
        with patch(f'{APPLICATION}.EmissionsReportExporter.build_csv_text',
                   return_value='normalized csv') as exporter:
            report = EmissionsApplicationService.build_csv_report(str(source), result)
            exporter.assert_called_once_with(valid_city(), result.emissions_data)
            for endpoint in ('/emissions?export=csv',
                             '/emissions/upload?export=csv'):
                response = self.post_city(endpoint, city)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_data(as_text=True), report['csv_text'])
            exporter.assert_called_once()
        self.assertEqual(city, original)
        self.assertEqual(source.read_bytes(), original_bytes)
