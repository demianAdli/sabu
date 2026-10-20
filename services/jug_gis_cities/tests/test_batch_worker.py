"""Tests for the persistent asynchronous FSA batch worker."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_SERVICE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..'))
if _SERVICE_ROOT not in sys.path:
    sys.path.insert(0, _SERVICE_ROOT)
_SABU_CHASSIS_SRC = os.path.join(_REPO_ROOT, 'libs', 'sabu_chassis', 'src')
if _SABU_CHASSIS_SRC not in sys.path:
    sys.path.insert(0, _SABU_CHASSIS_SRC)

from src.jug_gis_cities.application.batch_jobs import SqliteBatchJobStore
from src.jug_gis_cities.application.fsa_batch_runner import (
    FsaBatchItemResult,
    FsaBatchRunResult,
)
from src.jug_gis_cities import batch_worker
from src.jug_gis_cities.application.artifacts import ArtifactStore


class _FakeRunner:
    artifact_id = None

    def __init__(self, **kwargs):
        self.component_name = kwargs['component_name']
        self.mode = kwargs['mode']
        self.max_workers = kwargs['max_workers']
        self.result_callback = kwargs['result_callback']

    def validate_component(self):
        return None

    def resolve_fsas(self, fsas):
        return ('H3H', 'H2X') if fsas is None else tuple(fsas)

    def run(self, fsas):
        results = (
            FsaBatchItemResult(
                fsa='H3H',
                succeeded=True,
                workflow_output_path='H3H.gpkg',
                standardized_artifact_id=self.artifact_id),
            FsaBatchItemResult(
                fsa='H2X',
                succeeded=False,
                error='RuntimeError: boom'),
        )
        for result in reversed(results):
            self.result_callback(result)
        return FsaBatchRunResult(
            component_name=self.component_name,
            mode=self.mode,
            max_workers=self.max_workers,
            results=results)


class TestFsaBatchJobWorker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteBatchJobStore(
            os.path.join(self.temp_dir.name, 'jobs.sqlite3'))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_job(self):
        return self.store.create_job(
            component_name='future_fsa_gisoo',
            mode='standardize',
            requested_fsas=None,
            all_fsas=True,
            max_workers=3,
            cleanup_outputs=True,
            keep_outputs=('usage_clean',))

    @patch.object(batch_worker, 'FsaBatchRunner', _FakeRunner)
    def test_worker_persists_ordered_partial_failure_results(self):
        source = Path(self.temp_dir.name) / 'standardized.geojson'
        source.write_bytes(b'{"type":"FeatureCollection","features":[]}')
        artifacts = ArtifactStore(Path(self.temp_dir.name) / 'artifacts')
        artifact = artifacts.register(source, component_name='future_fsa_gisoo', fsa='H3H')
        created = self._create_job()
        worker = batch_worker.FsaBatchJobWorker(
            store=self.store,
            worker_id='worker-1')

        with patch.object(_FakeRunner, 'artifact_id', artifact.artifact_id):
            self.assertTrue(worker.run_once())

        completed = self.store.get_job(created.batch_id)
        self.assertEqual(completed.status, 'failed')
        self.assertEqual(completed.resolved_fsas, ('H3H', 'H2X'))
        self.assertEqual(
            tuple(result['fsa'] for result in completed.results),
            ('H3H', 'H2X'))
        self.assertEqual(completed.succeeded_count, 1)
        self.assertEqual(completed.failed_count, 1)
        restarted = SqliteBatchJobStore(self.store.path).get_job(created.batch_id)
        self.assertEqual(restarted.results[0]['standardized_artifact_id'], artifact.artifact_id)
        self.assertIsNone(restarted.results[1]['standardized_artifact_id'])
        _, stream = ArtifactStore(artifacts.directory).open_download(
            restarted.results[0]['standardized_artifact_id'])
        with stream:
            self.assertEqual(stream.read(), source.read_bytes())

    @patch.object(batch_worker, 'FsaBatchRunner', _FakeRunner)
    def test_worker_requeues_job_when_output_is_locked(self):
        created = self._create_job()
        self.store.acquire_fsa_locks(
            'another-job',
            created.component_name,
            ('H3H',))
        worker = batch_worker.FsaBatchJobWorker(
            store=self.store,
            worker_id='worker-1')

        self.assertTrue(worker.run_once())

        queued = self.store.get_job(created.batch_id)
        self.assertEqual(queued.status, 'queued')
        self.assertIn('output lock', queued.error)


if __name__ == '__main__':
    unittest.main()
