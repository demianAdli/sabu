"""Tests for safe Montreal FSA output cleanup."""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import call, patch


_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_SABU_CHASSIS_SRC = os.path.join(_REPO_ROOT, 'libs', 'sabu_chassis', 'src')
if _SABU_CHASSIS_SRC not in sys.path:
    sys.path.insert(0, _SABU_CHASSIS_SRC)

from src.jug_gis_cities.mtl_fsa_gisoo import output_cleanup
from src.jug_gis_cities.application.artifacts import ArtifactStore


class TestMtlFsaOutputCleanup(unittest.TestCase):
    def test_registered_copy_survives_cleanup_and_source_removal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / 'outputs'
            source_directory = output_root / 'H3H' / 'mtl_H3H_gisoo_standardized'
            source_directory.mkdir(parents=True)
            source = source_directory / 'standardized.geojson'
            content = b'{"type":"FeatureCollection","features":[]}'
            source.write_bytes(content)
            intermediate = output_root / 'H3H' / 'usage_clean'
            intermediate.mkdir()
            (intermediate / 'temporary.gpkg').touch()
            store = ArtifactStore(Path(temp_dir) / 'artifacts')
            artifact = store.register(source, component_name='mtl_fsa_gisoo', fsa='H3H')
            with patch.object(output_cleanup.paths, 'output_paths_dir', str(output_root)):
                output_cleanup.cleanup_outputs('H3H', release_qgis_layers=False)
            self.assertFalse(intermediate.exists())
            self.assertTrue(source.exists())
            source.unlink()
            _, stream = ArtifactStore(store.directory).open_download(artifact.artifact_id)
            with stream:
                self.assertEqual(stream.read(), content)

    @classmethod
    def tearDownClass(cls):
        """Avoid leaking environment-derived config into workflow tests."""
        package_name = 'src.jug_gis_cities.mtl_fsa_gisoo'
        package = sys.modules.get(package_name)
        if package is not None:
            package.__dict__.pop('workflow_config', None)
            package.__dict__.pop('output_cleanup', None)
        sys.modules.pop(f'{package_name}.workflow_config', None)
        sys.modules.pop(f'{package_name}.output_cleanup', None)

    def test_cleanup_retains_defaults_standardized_and_extra_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(output_cleanup.paths, 'output_paths_dir', temp_dir):
                fsa_root = Path(temp_dir, 'H3H')
                for output_key in output_cleanup.paths.output_paths:
                    resolved_key = output_key.format(fsa='H3H')
                    output_directory = fsa_root / resolved_key
                    output_directory.mkdir(parents=True)
                    (output_directory / f'{resolved_key}.gpkg').touch()

                standardized_directory = (
                    fsa_root / 'mtl_H3H_gisoo_standardized')
                (standardized_directory /
                 'mtl_H3H_gisoo_standardized.geojson').touch()

                deleted_paths = output_cleanup.cleanup_outputs(
                    'h3h',
                    keep_outputs=['usage_clean'])

                retained_keys = set(
                    output_cleanup.paths.default_retained_output_keys)
                retained_keys.add('usage_clean')
                for output_key in output_cleanup.paths.output_paths:
                    resolved_key = output_key.format(fsa='H3H')
                    self.assertEqual(
                        (fsa_root / resolved_key).exists(),
                        output_key in retained_keys)
                self.assertTrue(standardized_directory.exists())
                self.assertTrue(
                    (standardized_directory /
                     'mtl_H3H_gisoo_standardized.gpkg').exists())
                self.assertTrue(
                    (standardized_directory /
                     'mtl_H3H_gisoo_standardized.geojson').exists())
                self.assertEqual(
                    len(deleted_paths),
                    len(output_cleanup.paths.output_paths) -
                    len(retained_keys))

    def test_cleanup_rejects_unknown_keep_output_before_deleting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(output_cleanup.paths, 'output_paths_dir', temp_dir):
                with self.assertRaisesRegex(ValueError, 'Unknown.*output key'):
                    output_cleanup.cleanup_outputs(
                        'H3H',
                        keep_outputs=['not_a_workflow_output'])

    def test_cleanup_can_skip_qgis_import_for_isolated_parent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(output_cleanup.paths, 'output_paths_dir', temp_dir):
                with patch.object(
                        output_cleanup,
                        '_release_qgis_output_layers') as release_mock:
                    output_cleanup.cleanup_outputs(
                        'H3H',
                        release_qgis_layers=False)

        release_mock.assert_not_called()

    def test_cleanup_refuses_configured_path_outside_fsa_root(self):
        configured_outputs = dict(output_cleanup.paths.output_paths)
        configured_outputs['../outside'] = ''
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(output_cleanup.paths, 'output_paths_dir', temp_dir):
                with patch.object(
                        output_cleanup.paths,
                        'output_paths',
                        configured_outputs):
                    with self.assertRaisesRegex(
                            ValueError,
                            'Refusing to clean'):
                        output_cleanup.cleanup_outputs('H3H')

    def test_remove_output_directory_retries_windows_file_lock(self):
        output_directory = Path('locked_output')
        with patch.object(
                output_cleanup.shutil,
                'rmtree',
                side_effect=[PermissionError(), PermissionError(), None]
        ) as rmtree_mock:
            with patch.object(output_cleanup.time, 'sleep') as sleep_mock:
                output_cleanup._remove_output_directory(output_directory)

        self.assertEqual(
            rmtree_mock.call_args_list,
            [call(output_directory), call(output_directory), call(output_directory)])
        self.assertEqual(
            sleep_mock.call_args_list,
            [call(0.1), call(0.25)])

    def test_release_qgis_output_layers_only_removes_selected_fsa_layers(self):
        class _FakeLayer:
            def __init__(self, source):
                self._source = source

            def source(self):
                return self._source

        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir, 'H3H').resolve()
            inside_path = output_root / 'inter_kept' / 'inter_kept.gpkg'
            outside_path = Path(temp_dir, 'H2X', 'roll', 'roll.gpkg')
            project = unittest.mock.Mock()
            project.mapLayers.return_value = {
                'inside': _FakeLayer(f'{inside_path}|layername=inter_kept'),
                'outside': _FakeLayer(os.fspath(outside_path)),
            }
            fake_qgis = types.ModuleType('qgis')
            fake_qgis_core = types.ModuleType('qgis.core')
            fake_qgis_core.QgsProject = unittest.mock.Mock()
            fake_qgis_core.QgsProject.instance.return_value = project

            with patch.dict(
                    sys.modules,
                    {'qgis': fake_qgis, 'qgis.core': fake_qgis_core}):
                released_count = output_cleanup._release_qgis_output_layers(
                    output_root)

        self.assertEqual(released_count, 1)
        project.removeMapLayers.assert_called_once_with(['inside'])


if __name__ == '__main__':
    unittest.main()
