"""Consistency checks for runtime batch payloads and repository contracts."""
import json
import os
import sys
import tempfile
import unittest


_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_SERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _SERVICE_ROOT not in sys.path:
    sys.path.insert(0, _SERVICE_ROOT)
_SABU_CHASSIS_SRC = os.path.join(_REPO_ROOT, 'libs', 'sabu_chassis', 'src')
if _SABU_CHASSIS_SRC not in sys.path:
    sys.path.insert(0, _SABU_CHASSIS_SRC)

from src.jug_gis_cities.application.batch_jobs import SqliteBatchJobStore


_CONTRACT_ROOT = os.path.join(_REPO_ROOT, 'contracts')


def _load_json(*parts):
    path = os.path.join(_CONTRACT_ROOT, *parts)
    with open(path, encoding='utf-8-sig') as source:
        return json.load(source)


class TestFsaBatchContracts(unittest.TestCase):
    def test_runtime_job_has_exact_json_schema_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SqliteBatchJobStore(
                os.path.join(temp_dir, 'jobs.sqlite3'))
            response = store.create_job(
                component_name='mtl_fsa_gisoo',
                mode='standardize',
                requested_fsas=None,
                all_fsas=True,
                max_workers=3,
                cleanup_outputs=True,
                keep_outputs=('usage_clean',)).to_response()

        schema = _load_json(
            'jsonschema',
            'jug_gis_cities',
            'batch_job.schema.json')
        self.assertEqual(set(response), set(schema['properties']))
        self.assertTrue(set(schema['required']).issubset(response))

    def test_batch_examples_match_declared_job_fields(self):
        schema = _load_json(
            'jsonschema',
            'jug_gis_cities',
            'batch_job.schema.json')
        expected_fields = set(schema['properties'])

        for filename in (
                'api_batch_all_fsas.response.202.json',
                'api_batch_status.response.200.json'):
            with self.subTest(filename=filename):
                example = _load_json(
                    'examples',
                    'jug_gis_cities',
                    filename)
                self.assertEqual(set(example), expected_fields)

    def test_single_run_examples_include_cleanup_metadata(self):
        for filename in (
                'api_run_independent.response.201.json',
                'api_run_mtl_fsa_independent.response.201.json',
                'api_run_standardize.response.201.json'):
            with self.subTest(filename=filename):
                example = _load_json(
                    'examples',
                    'jug_gis_cities',
                    filename)
                self.assertIn('cleaned_output_paths', example)

    def test_openapi_declares_batch_operations_and_schemas(self):
        try:
            import yaml
        except ModuleNotFoundError as exc:
            self.skipTest(f'PyYAML is required for OpenAPI parsing: {exc}')

        openapi_path = os.path.join(
            _CONTRACT_ROOT,
            'openapi',
            'jug_gis_cities.yaml')
        with open(openapi_path, encoding='utf-8') as source:
            contract = yaml.safe_load(source)

        self.assertIn(
            '/components/{component_name}/batch-runs',
            contract['paths'])
        self.assertIn(
            '/components/{component_name}/batch-runs/{batch_id}',
            contract['paths'])
        self.assertIn('FsaBatchRunRequest', contract['components']['schemas'])
        self.assertIn('FsaBatchJob', contract['components']['schemas'])

    def test_examples_validate_against_json_schemas(self):
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ModuleNotFoundError as exc:
            self.skipTest(f'jsonschema is required: {exc}')
        examples = {
            'standardized_output_response.schema.json': [
                'api_run_standardize.response.201.json'],
            'independent_workflow_output_response.schema.json': [
                'api_run_independent.response.201.json',
                'api_run_mtl_fsa_independent.response.201.json'],
            'batch_job.schema.json': [
                'api_batch_all_fsas.response.202.json',
                'api_batch_status.response.200.json'],
            'error_response.schema.json': [
                'error.response.404.artifact_not_found.json',
                'error.response.410.artifact_unavailable.json'],
        }
        for schema_name, filenames in examples.items():
            schema = _load_json('jsonschema', 'jug_gis_cities', schema_name)
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            for filename in filenames:
                with self.subTest(filename=filename):
                    validator.validate(_load_json('examples', 'jug_gis_cities', filename))

    def test_runtime_and_documented_artifact_contracts_match(self):
        try:
            import yaml
            from flask import Flask
            from flask_smorest import Api
        except ModuleNotFoundError as exc:
            self.skipTest(f'API contract dependencies are required: {exc}')
        from src.jug_gis_cities.resources.gis_components import blp

        app = Flask(__name__)
        app.config.update(API_TITLE='Test', API_VERSION='v1', OPENAPI_VERSION='3.0.2')
        api = Api(app)
        api.register_blueprint(blp)
        runtime = api.spec.to_dict()
        with open(os.path.join(_CONTRACT_ROOT, 'openapi', 'jug_gis_cities.yaml'),
                  encoding='utf-8') as source:
            documented = yaml.safe_load(source)
        path = '/artifacts/{artifact_id}/download'
        for contract in (runtime, documented):
            responses = contract['paths'][path]['get']['responses']
            self.assertTrue({'200', '404', '410', '500'}.issubset(responses))
            self.assertEqual(
                responses['200']['content']['application/geo+json']['schema'],
                {'type': 'string', 'format': 'binary'})
        for runtime_name, documented_name in (
                ('GISComponentRunResult', 'GISComponentRunResponse'),
                ('FsaBatchItemResult', 'FsaBatchItemResult')):
            actual = runtime['components']['schemas'][runtime_name]
            expected = documented['components']['schemas'][documented_name]
            self.assertEqual(set(actual['properties']), set(expected['properties']))
            for field in ('standardized_artifact_id', 'standardized_download_url'):
                self.assertIn(field, actual['required'])
                self.assertIn(field, expected['required'])
                self.assertEqual(actual['properties'][field],
                                 {key: value for key, value in expected['properties'][field].items()
                                  if key != 'description'})


if __name__ == '__main__':
    unittest.main()
