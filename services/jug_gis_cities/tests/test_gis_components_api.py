"""
Sabu project
jug_gis_cities package
test_gis_components_api module
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import unittest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_SABU_CHASSIS_SRC = os.path.join(_REPO_ROOT, 'libs', 'sabu_chassis', 'src')
if _SABU_CHASSIS_SRC not in sys.path:
    sys.path.insert(0, _SABU_CHASSIS_SRC)

try:
    from flask import Flask
    from flask_smorest import Api
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(
        'Flask service dependencies are required for API tests.'
    ) from exc

from src.jug_gis_cities.application import (
    GisComponentContractError,
    GisComponentError,
    GisComponentNotFoundError,
    GisComponentRunMode,
    GisComponentRunResult,
)
from src.jug_gis_cities.resources.gis_components import (
    blp as gis_components_blueprint,
)
from src.jug_gis_cities.application.batch_jobs import get_batch_job_store
from src.jug_gis_cities.application.artifacts import ArtifactError, get_artifact_store


def _build_test_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['API_TITLE'] = 'GIS Cities Workflow API'
    app.config['API_VERSION'] = 'v1'
    app.config['OPENAPI_VERSION'] = '3.0.2'

    api = Api(app)
    api.register_blueprint(gis_components_blueprint)
    return app


class TestGISComponentsApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.job_store_env = patch.dict(
            os.environ,
            {'JUG_GIS_CITIES_ARTIFACT_DIR': os.path.join(self.temp_dir.name, 'artifacts'),
             'JUG_GIS_CITIES_JOB_STORE_PATH': os.path.join(
                self.temp_dir.name,
                'jobs.sqlite3')})
        self.job_store_env.start()
        self.app = _build_test_app()
        self.client = self.app.test_client()

    def tearDown(self):
        self.job_store_env.stop()
        self.temp_dir.cleanup()

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'GISCitiesApplicationService.run_component'
    )
    def test_post_component_run_json_contract(self, run_component_mock):
        run_component_mock.return_value = GisComponentRunResult(
            component_name='saint_malachie_gisoo',
            mode=GisComponentRunMode.STANDARDIZE,
            workflow_output_path='workflow_output.shp',
            standardized_output_path='standardized.geojson',
            standardized_artifact_id='a' * 32)

        response = self.client.post(
            '/components/saint_malachie_gisoo/runs',
            json={'mode': 'standardize'})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json(),
            {
                'component_name': 'saint_malachie_gisoo',
                'mode': 'standardize',
                'fsa': None,
                'workflow_output_path': 'workflow_output.shp',
                'standardized_output_path': 'standardized.geojson',
                'standardized_artifact_id': 'a' * 32,
                'standardized_download_url': f'http://localhost/artifacts/{"a" * 32}/download',
                'cleaned_output_paths': [],
            })
        run_component_mock.assert_called_once_with(
            component_name='saint_malachie_gisoo',
            mode='standardize',
            fsa=None,
            non_null_required_fields=None,
            cleanup_outputs=False,
            keep_outputs=None)

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'GISCitiesApplicationService.run_component'
    )
    def test_post_component_run_accepts_fsa(self, run_component_mock):
        run_component_mock.return_value = GisComponentRunResult(
            component_name='mtl_fsa_gisoo',
            mode=GisComponentRunMode.INDEPENDENT,
            fsa='H3H',
            workflow_output_path='workflow_output.shp',
            standardized_output_path=None)

        response = self.client.post(
            '/components/mtl_fsa_gisoo/runs',
            json={'mode': 'independent', 'fsa': 'h3h'})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json(),
            {
                'component_name': 'mtl_fsa_gisoo',
                'mode': 'independent',
                'fsa': 'H3H',
                'workflow_output_path': 'workflow_output.shp',
                'standardized_output_path': None,
                'standardized_artifact_id': None,
                'standardized_download_url': None,
                'cleaned_output_paths': [],
            })
        run_component_mock.assert_called_once_with(
            component_name='mtl_fsa_gisoo',
            mode='independent',
            fsa='h3h',
            non_null_required_fields=None,
            cleanup_outputs=False,
            keep_outputs=None)

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'GISCitiesApplicationService.run_component'
    )
    def test_post_component_run_accepts_drop_null_fields(
            self,
            run_component_mock):
        run_component_mock.return_value = GisComponentRunResult(
            component_name='mtl_fsa_gisoo',
            mode=GisComponentRunMode.STANDARDIZE,
            fsa='H3H',
            workflow_output_path='workflow_output.gpkg',
            standardized_output_path='standardized.geojson')

        response = self.client.post(
            '/components/mtl_fsa_gisoo/runs',
            json={
                'mode': 'standardize',
                'fsa': 'h3h',
                'drop_null_fields': ['citygisoo_id', 'FSA'],
            })

        self.assertEqual(response.status_code, 201)
        run_component_mock.assert_called_once_with(
            component_name='mtl_fsa_gisoo',
            mode='standardize',
            fsa='h3h',
            non_null_required_fields=['citygisoo_id', 'FSA'],
            cleanup_outputs=False,
            keep_outputs=None)

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'GISCitiesApplicationService.run_component'
    )
    def test_post_component_run_accepts_cleanup_options(
            self,
            run_component_mock):
        run_component_mock.return_value = GisComponentRunResult(
            component_name='mtl_fsa_gisoo',
            mode=GisComponentRunMode.INDEPENDENT,
            fsa='H3H',
            workflow_output_path='workflow_output.gpkg',
            cleaned_output_paths=('usage_clean',))

        response = self.client.post(
            '/components/mtl_fsa_gisoo/runs',
            json={
                'mode': 'independent',
                'fsa': 'h3h',
                'cleanup_outputs': True,
                'keep_outputs': ['inter_summary'],
            })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json()['cleaned_output_paths'],
            ['usage_clean'])
        run_component_mock.assert_called_once_with(
            component_name='mtl_fsa_gisoo',
            mode='independent',
            fsa='h3h',
            non_null_required_fields=None,
            cleanup_outputs=True,
            keep_outputs=['inter_summary'])

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'GISCitiesApplicationService.run_component'
    )
    def test_post_component_run_not_found(self, run_component_mock):
        run_component_mock.side_effect = GisComponentNotFoundError(
            'GIS city component not found: missing_component')

        response = self.client.post(
            '/components/missing_component/runs',
            json={'mode': 'standardize'})

        self.assertEqual(response.status_code, 404)
        self.assertIn('missing_component', response.get_data(as_text=True))

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'GISCitiesApplicationService.run_component'
    )
    def test_post_component_run_contract_error(self, run_component_mock):
        run_component_mock.side_effect = GisComponentContractError(
            'GIS city component mtl_gisoo is missing contract_adapter.py.')

        response = self.client.post(
            '/components/mtl_gisoo/runs',
            json={'mode': 'standardize'})

        self.assertEqual(response.status_code, 422)
        self.assertIn('contract_adapter.py',
                      response.get_data(as_text=True))

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'GISCitiesApplicationService.run_component'
    )
    def test_post_component_run_bad_request(self, run_component_mock):
        run_component_mock.side_effect = ValueError(
            'Unsupported GIS component mode: finalize.')

        response = self.client.post(
            '/components/saint_malachie_gisoo/runs',
            json={'mode': 'standardize'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('Unsupported GIS component mode',
                      response.get_data(as_text=True))

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'GISCitiesApplicationService.run_component'
    )
    def test_post_component_run_execution_error(self, run_component_mock):
        run_component_mock.side_effect = GisComponentError(
            'GIS city component execution failed: saint_malachie_gisoo')

        response = self.client.post(
            '/components/saint_malachie_gisoo/runs',
            json={'mode': 'standardize'})

        self.assertEqual(response.status_code, 500)
        self.assertIn('GIS city component execution failed',
                      response.get_data(as_text=True))

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'FsaBatchRunner.validate_component'
    )
    def test_submit_and_get_all_fsa_batch(self, validate_component_mock):
        response = self.client.post(
            '/components/future_fsa_gisoo/batch-runs',
            json={
                'mode': 'standardize',
                'all_fsas': True,
                'max_workers': 3,
                'cleanup_outputs': True,
                'keep_outputs': ['usage_clean'],
            })

        self.assertEqual(response.status_code, 202)
        submitted = response.get_json()
        self.assertEqual(submitted['status'], 'queued')
        self.assertEqual(submitted['component_name'], 'future_fsa_gisoo')
        self.assertTrue(submitted['all_fsas'])
        self.assertIsNone(submitted['fsas'])
        self.assertEqual(submitted['max_workers'], 3)
        self.assertEqual(submitted['completed_count'], 0)

        status_response = self.client.get(
            '/components/future_fsa_gisoo/batch-runs/'
            f"{submitted['batch_id']}")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.get_json(), submitted)
        validate_component_mock.assert_called_once_with()

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'FsaBatchRunner.validate_component'
    )
    def test_submit_selected_fsas_normalizes_and_deduplicates(
            self,
            validate_component_mock):
        response = self.client.post(
            '/components/future_fsa_gisoo/batch-runs',
            json={
                'fsas': ['h3h', 'H2X', 'H3H'],
                'max_workers': 3,
            })

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()['fsas'], ['H3H', 'H2X'])
        validate_component_mock.assert_called_once_with()

    def test_batch_submission_requires_one_fsa_selection(self):
        missing = self.client.post(
            '/components/future_fsa_gisoo/batch-runs',
            json={'max_workers': 3})
        both = self.client.post(
            '/components/future_fsa_gisoo/batch-runs',
            json={'fsas': ['H3H'], 'all_fsas': True})

        self.assertEqual(missing.status_code, 422)
        self.assertEqual(both.status_code, 422)

    def test_get_unknown_batch_returns_not_found(self):
        response = self.client.get(
            '/components/future_fsa_gisoo/batch-runs/missing')

        self.assertEqual(response.status_code, 404)

    def _register_artifact(self):
        source = Path(self.temp_dir.name) / 'standardized.geojson'
        source.write_bytes(b'{"type":"FeatureCollection","features":[]}')
        artifact = get_artifact_store().register(
            source, component_name='mtl_fsa_gisoo', fsa='H3H')
        return artifact, source

    @patch('src.jug_gis_cities.resources.gis_components.GISCitiesApplicationService.run_component')
    def test_download_existing_artifact_repeatedly_without_execution(self, run_mock):
        artifact, source = self._register_artifact()
        content = source.read_bytes()
        source.unlink()
        for _ in range(2):
            with self.client.get(f'/artifacts/{artifact.artifact_id}/download') as response:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, content)
                self.assertEqual(response.mimetype, 'application/geo+json')
                self.assertEqual(response.content_length, len(content))
                self.assertIn('attachment;', response.headers['Content-Disposition'])
                self.assertIn(artifact.artifact_id, response.headers['Content-Disposition'])
        run_mock.assert_not_called()

    def test_unknown_missing_and_unregistered_artifacts(self):
        artifact, _ = self._register_artifact()
        path = get_artifact_store().directory / artifact.artifact_id / 'output.geojson'
        path.unlink()
        missing = self.client.get(f'/artifacts/{artifact.artifact_id}/download')
        self.assertEqual(missing.status_code, 410)
        self.assertEqual(missing.get_json()['message'], 'Artifact is unavailable.')
        for artifact_id in ('unknown', 'f' * 32):
            self.assertEqual(self.client.get(
                f'/artifacts/{artifact_id}/download').status_code, 404)
        unregistered = get_artifact_store().directory / ('f' * 32)
        unregistered.mkdir()
        (unregistered / 'output.geojson').write_bytes(b'not registered')
        self.assertEqual(self.client.get(
            f'/artifacts/{"f" * 32}/download').status_code, 404)

    def test_download_cannot_select_a_filesystem_path(self):
        artifact, source = self._register_artifact()
        registered_content = source.read_bytes()
        source.write_bytes(b'private file that must not be served')
        with self.client.get(
                f'/artifacts/{artifact.artifact_id}/download',
                query_string={'path': str(source), 'filename': str(source)}) as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, registered_content)
        self.assertEqual(self.client.get(
            '/artifacts/..%2Fstandardized.geojson/download').status_code, 404)

    @patch('src.jug_gis_cities.resources.gis_components.get_artifact_store')
    def test_store_failure_does_not_disclose_filesystem_paths(self, store_mock):
        store_mock.side_effect = ArtifactError('private directory')
        response = self.client.get(f'/artifacts/{"a" * 32}/download')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private directory', response.get_data(as_text=True))

    def test_rerun_returns_new_id_and_old_download_survives_app_restart(self):
        source = Path(self.temp_dir.name) / 'standardized.geojson'
        source.write_bytes(b'first GeoJSON bytes')
        application = (
            'src.jug_gis_cities.application.jug_gis_cities.GISCitiesApplicationService.')
        with patch(application + '_normalize_component_name',
                   return_value='saint_malachie_gisoo'), \
                patch(application + '_ensure_component_callable'), \
                patch(application + '_import_component_callable') as import_mock:
            from unittest.mock import Mock
            workflow = Mock(return_value='raw.shp')
            adapter = Mock(return_value=str(source))
            import_mock.side_effect = [workflow, adapter, workflow, adapter]
            first = self.client.post('/components/saint_malachie_gisoo/runs', json={})
            self.assertEqual(first.status_code, 201)
            source.write_bytes(b'second GeoJSON bytes')
            second = self.client.post('/components/saint_malachie_gisoo/runs', json={})
            self.assertEqual(second.status_code, 201)
            self.assertNotEqual(first.json['standardized_artifact_id'],
                                second.json['standardized_artifact_id'])
            restarted_client = _build_test_app().test_client()
            with restarted_client.get(first.json['standardized_download_url']) as download:
                self.assertEqual(download.data, b'first GeoJSON bytes')
            with restarted_client.get(second.json['standardized_download_url']) as download:
                self.assertEqual(download.data, b'second GeoJSON bytes')
            self.assertEqual(workflow.call_count, 2)
            self.assertEqual(adapter.call_count, 2)

    def test_partial_batch_download_after_restart_and_legacy_results(self):
        artifact, source = self._register_artifact()
        store = get_batch_job_store()
        job = store.create_job(
            component_name='mtl_fsa_gisoo', mode='standardize',
            requested_fsas=('H3H', 'H2X'), all_fsas=False, max_workers=1,
            non_null_required_fields=None, cleanup_outputs=False, keep_outputs=None)
        store.set_results(job.batch_id, [
            {'fsa': 'H3H', 'succeeded': True, 'workflow_output_path': 'raw.gpkg',
             'standardized_output_path': str(source), 'cleaned_output_paths': [],
             'error': None, 'elapsed_seconds': 1.0,
             'standardized_artifact_id': artifact.artifact_id},
            {'fsa': 'H2X', 'succeeded': False, 'workflow_output_path': None,
             'standardized_output_path': None, 'cleaned_output_paths': [],
             'error': 'failed', 'elapsed_seconds': 1.0}])
        store.complete_job(job.batch_id, False)
        client = _build_test_app().test_client()
        response = client.get(f'/components/mtl_fsa_gisoo/batch-runs/{job.batch_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'failed')
        successful, failed = response.json['results']
        self.assertEqual(successful['standardized_artifact_id'], artifact.artifact_id)
        self.assertIsNone(failed['standardized_download_url'])
        with client.get(successful['standardized_download_url']) as download:
            self.assertEqual(download.data, source.read_bytes())
        # Existing successful records have no registration to retroactively expose.
        legacy_result = dict(store.get_job(job.batch_id).results[0])
        legacy_result.pop('standardized_artifact_id')
        store.set_results(job.batch_id, [legacy_result])
        response = client.get(f'/components/mtl_fsa_gisoo/batch-runs/{job.batch_id}')
        self.assertIsNone(response.json['results'][0]['standardized_download_url'])

    @patch(
        'src.jug_gis_cities.resources.gis_components.'
        'GISCitiesApplicationService.run_component'
    )
    def test_single_fsa_run_rejects_conflicting_batch_lock(
            self,
            run_component_mock):
        store = get_batch_job_store()
        self.assertTrue(store.acquire_fsa_locks(
            'existing-batch',
            'mtl_fsa_gisoo',
            ('H3H',)))

        response = self.client.post(
            '/components/mtl_fsa_gisoo/runs',
            json={'mode': 'independent', 'fsa': 'h3h'})

        self.assertEqual(response.status_code, 409)
        run_component_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
