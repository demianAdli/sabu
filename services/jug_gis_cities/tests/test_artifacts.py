"""Artifact persistence and file isolation without a GIS runtime."""
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / 'libs' / 'sabu_chassis' / 'src'))

from src.jug_gis_cities.application.artifacts import (
    ArtifactError,
    ArtifactNotFoundError,
    ArtifactStore,
    ArtifactUnavailableError,
    get_artifact_store,
)


class TestArtifacts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'standardized.geojson'
        self.source.write_bytes(b'{"type":"FeatureCollection","features":[]}')
        self.store = ArtifactStore(self.root / 'artifacts')

    def register(self):
        return self.store.register(
            self.source, component_name='mtl_fsa_gisoo', fsa='H3H')

    def read(self, artifact_id, store=None):
        artifact, stream = (store or self.store).open_download(artifact_id)
        with stream:
            return artifact, stream.read()

    def test_rerun_and_source_deletion_preserve_original_bytes(self):
        original_bytes = self.source.read_bytes()
        first = self.register()
        self.source.write_bytes(b'{"type":"FeatureCollection","features":[1]}')
        second_bytes = self.source.read_bytes()
        second = self.register()
        self.source.unlink()
        self.assertNotEqual(first.artifact_id, second.artifact_id)
        self.assertEqual(self.read(first.artifact_id)[1], original_bytes)
        self.assertEqual(self.read(second.artifact_id)[1], second_bytes)

    def test_recreated_store_retains_registration_and_copy(self):
        artifact = self.register()
        restored, content = self.read(
            artifact.artifact_id, ArtifactStore(self.store.directory))
        self.assertEqual(restored, artifact)
        self.assertEqual(content, self.source.read_bytes())

    def test_failed_copy_is_not_registered_or_left_downloadable(self):
        with patch(
                'src.jug_gis_cities.application.artifacts.os.fsync',
                side_effect=OSError('disk full')):
            with self.assertRaises(ArtifactError):
                self.register()
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            self.assertEqual(connection.execute(
                'SELECT count(*) FROM artifacts').fetchone()[0], 0)
        self.assertFalse(any(p.is_dir() for p in self.store.directory.iterdir()))

    def test_registration_failure_does_not_return_success(self):
        self.source.unlink()
        with self.assertRaises(ArtifactError):
            self.register()

    def test_database_failure_removes_unregistered_completed_copy(self):
        with patch.object(self.store, '_connect',
                          side_effect=sqlite3.OperationalError('database failure')):
            with self.assertRaises(ArtifactError):
                self.register()
        self.assertFalse(any(p.is_dir() for p in self.store.directory.iterdir()))

    def test_id_collision_cannot_overwrite_existing_copy(self):
        first = self.register()
        self.source.write_bytes(b'changed')
        with patch('src.jug_gis_cities.application.artifacts.uuid.uuid4') as uuid_mock:
            uuid_mock.return_value.hex = first.artifact_id
            with self.assertRaises(ArtifactError):
                self.register()
        self.assertNotEqual(self.read(first.artifact_id)[1], b'changed')

    def test_concurrent_registrations_remain_independent(self):
        def register(_):
            return ArtifactStore(self.store.directory).register(
                self.source, component_name='mtl_fsa_gisoo')
        with ThreadPoolExecutor(max_workers=3) as executor:
            artifacts = list(executor.map(register, range(6)))
        self.assertEqual(len({item.artifact_id for item in artifacts}), 6)
        for artifact in artifacts:
            self.assertEqual(self.read(artifact.artifact_id)[1], self.source.read_bytes())

    def test_unregistered_file_and_arbitrary_paths_are_not_downloadable(self):
        artifact_id = 'a' * 32
        directory = self.store.directory / artifact_id
        directory.mkdir()
        (directory / 'output.geojson').write_bytes(b'unregistered')
        for value in (artifact_id, '../standardized.geojson', str(self.source), 'bad'):
            with self.subTest(value=value), self.assertRaises(ArtifactNotFoundError):
                self.store.open_download(value)

    def test_missing_or_truncated_registered_file_is_unavailable(self):
        artifact = self.register()
        path = self.store.directory / artifact.artifact_id / 'output.geojson'
        path.write_bytes(b'truncated')
        with self.assertRaises(ArtifactUnavailableError):
            self.store.open_download(artifact.artifact_id)
        path.unlink()
        with self.assertRaises(ArtifactUnavailableError):
            self.store.open_download(artifact.artifact_id)

    def test_symlink_escape_is_unavailable(self):
        artifact = self.register()
        path = self.store.directory / artifact.artifact_id / 'output.geojson'
        path.unlink()
        try:
            path.symlink_to(self.source)
        except OSError as exc:
            self.skipTest(f'Symlink creation is unavailable: {exc}')
        with self.assertRaises(ArtifactUnavailableError):
            self.store.open_download(artifact.artifact_id)

    def test_read_failure_is_reported_without_exposing_path(self):
        artifact = self.register()
        with patch('src.jug_gis_cities.application.artifacts.os.open',
                   side_effect=PermissionError('private path')):
            with self.assertRaisesRegex(ArtifactError, '^Failed to read artifact.$'):
                self.store.open_download(artifact.artifact_id)

    def test_default_location_follows_persistent_job_store(self):
        with patch.dict(os.environ, {'JUG_GIS_CITIES_JOB_STORE_PATH':
                                    str(self.root / 'jobs.sqlite3')}):
            with patch.dict(os.environ) as environment:
                environment.pop('JUG_GIS_CITIES_ARTIFACT_DIR', None)
                store = get_artifact_store()
        self.assertEqual(store.directory, self.root / 'jug_gis_cities_artifacts')


if __name__ == '__main__':
    unittest.main()
