import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_uniquification_application import (
    REPO_ROOT, SERVICE_ROOT, SKIP_REASON, buildings_payload, no_validation_processing, run_standalone,
)
import test_uniquification_cli as cli_tests


@unittest.skipIf(SKIP_REASON, SKIP_REASON)
class TestUniquificationAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('uniquification_test_app', SERVICE_ROOT / 'app.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.app.testing = True
        cls.app = module.app

    def setUp(self):
        self.client = self.app.test_client()
        self.payload = {'buildings_set': buildings_payload(),
                        'unique_attribute_key': 'roll_id', 'area_key': 'rank_area'}

    def test_api_cli_and_application_results_are_equal_without_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.geojson'
            path.write_text(json.dumps(self.payload['buildings_set']), encoding='utf-8')
            with no_validation_processing():
                response = self.client.post('/uniquifications', json=self.payload)
                path_response = self.client.post('/uniquifications', json={
                    'buildings_set_path': str(path), 'unique_attribute_key': 'roll_id',
                    'area_key': 'rank_area'})
                code, stdout, stderr = cli_tests.TestUniquificationCLI().invoke([
                    'uniquify', '--buildings-set', str(path), '--unique-attribute-key',
                    'roll_id', '--area-key', 'rank_area'])
                expected = run_standalone(self.payload['buildings_set']).as_dict()
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(path_response.status_code, 200, path_response.get_json())
        self.assertEqual(code, 0, stderr)
        self.assertEqual(response.get_json(), expected)
        self.assertEqual(path_response.get_json(), expected)
        self.assertEqual(json.loads(stdout), expected)
        self.assertTrue(response.headers['X-Request-ID'])

    def test_request_errors(self):
        invalid = [
            {}, {'unique_attribute_key': 'roll_id'},
            dict(self.payload, buildings_set_path='also.geojson'),
            dict(self.payload, unique_attribute_key=''),
            dict(self.payload, area_key='  '),
            dict(self.payload, include_plot=True),
            dict(self.payload, census_data_csv='census.csv'),
            dict(self.payload, buildings_set=[]),
            {'buildings_set_path': '', 'unique_attribute_key': 'roll_id'},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                response = self.client.post('/uniquifications', json=payload)
                self.assertEqual(response.status_code, 422, response.get_json())
                self.assertIn('errors', response.get_json())
        self.assertEqual(self.client.post('/uniquifications', data='{',
                                         content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/uniquifications?export=plot',
                                         json=self.payload).status_code, 400)

    def test_default_area_key_and_nonfinite_singletons(self):
        payload = json.loads((REPO_ROOT / 'contracts/examples/jug_gis_validation/'
                             'uniquifications.request.json').read_text())
        payload.pop('area_key')
        # Null areas on missing identifiers must not become duplicate errors.
        payload['buildings_set']['features'][-1]['properties']['area'] = float('inf')
        response = self.client.post('/uniquifications', json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body['uniquification']['ranking_area_key'], 'area')
        self.assertIsNone(body['records'][-1]['area'])
        json.dumps(body, allow_nan=False)

    def test_input_and_policy_errors(self):
        response = self.client.post('/uniquifications', json={
            'buildings_set_path': 'missing.geojson', 'unique_attribute_key': 'roll_id'})
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/uniquifications', json=dict(self.payload, area_key='absent'))
        self.assertEqual(response.status_code, 422)
        self.assertIn('absent', response.get_json()['message'])
        self.payload['buildings_set']['features'][0]['properties']['rank_area'] = None
        response = self.client.post('/uniquifications', json=self.payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn('Duplicate', response.get_json()['message'])
        self.payload['buildings_set']['features'][0]['properties']['roll_id'] = ['unhashable']
        response = self.client.post('/uniquifications', json=self.payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn('input position 0', response.get_json()['message'])

    def test_unexpected_error_uses_generic_message(self):
        with patch('jug_gis_validation.resources.uniquifications.'
                   'GISUniquificationApplicationService.run_uniquification',
                   side_effect=RuntimeError('private details')):
            response = self.client.post('/uniquifications', json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['message'], 'Failed to run GIS uniquification')

    def test_runtime_openapi_documents_operation(self):
        spec = self.client.get('/openapi.json').get_json()
        operation = spec['paths']['/uniquifications']['post']
        self.assertIn('200', operation['responses'])
        self.assertIn('application/json', operation['requestBody']['content'])

    def test_contract_examples_and_live_response(self):
        try:
            from jsonschema import Draft202012Validator
            from referencing import Registry, Resource
            import yaml
        except ModuleNotFoundError as exc:
            self.skipTest(f'Optional contract test dependency is not installed: {exc.name}')
        contract_dir = REPO_ROOT / 'contracts/jsonschema/jug_gis_validation'
        schemas = [json.loads(path.read_text()) for path in contract_dir.glob('*.schema.json')]
        registry = Registry().with_resources(
            (schema['$id'], Resource.from_contents(schema)) for schema in schemas)
        for schema in schemas:
            Draft202012Validator.check_schema(schema)
        by_name = {schema['$id'].split('/')[-1]: schema for schema in schemas}
        def validate(name, instance):
            Draft202012Validator(by_name[name], registry=registry).validate(instance)
        examples = REPO_ROOT / 'contracts/examples/jug_gis_validation'
        request_payload = json.loads((examples / 'uniquifications.request.json').read_text())
        expected = json.loads((examples / 'uniquifications.response.200.json').read_text())
        validate('uniquification_request.schema.json', request_payload)
        validate('uniquification_request.schema.json', {
            'buildings_set_path': 'input.geojson', 'unique_attribute_key': 'roll_id'})
        validate('uniquification_response.schema.json', expected)
        validate('error_response.schema.json', json.loads(
            (examples / 'uniquifications.response.422.json').read_text()))
        response = self.client.post('/uniquifications', json=request_payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), expected)
        validate('uniquification_response.schema.json', response.get_json())
        spec = yaml.safe_load((REPO_ROOT / 'contracts/openapi/jug_gis_validation.yaml').read_text())
        self.assertIn('/uniquifications', spec['paths'])


if __name__ == '__main__':
    unittest.main()
