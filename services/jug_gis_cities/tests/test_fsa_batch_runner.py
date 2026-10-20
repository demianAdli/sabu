"""Tests for generic FSA component batch orchestration."""
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch


_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_SERVICE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..'))
if _SERVICE_ROOT not in sys.path:
    sys.path.insert(0, _SERVICE_ROOT)
_SABU_CHASSIS_SRC = os.path.join(_REPO_ROOT, 'libs', 'sabu_chassis', 'src')
if _SABU_CHASSIS_SRC not in sys.path:
    sys.path.insert(0, _SABU_CHASSIS_SRC)

from src.jug_gis_cities.application import fsa_batch_runner
from src.jug_gis_cities.application.fsa_batch_runner import (
    FsaBatchItemResult,
    FsaBatchRunner,
    discover_component_fsas,
    normalize_fsas,
    run_fsa_batch,
)
from src.jug_gis_cities.application.jug_gis_cities import (
    GisComponentContractError,
)


class _ComponentResult:
    def __init__(
            self,
            workflow_output_path,
            standardized_output_path=None,
            cleaned_output_paths=(),
            standardized_artifact_id=None):
        self.workflow_output_path = workflow_output_path
        self.standardized_output_path = standardized_output_path
        self.cleaned_output_paths = cleaned_output_paths
        self.standardized_artifact_id = standardized_artifact_id


class _FeatureLayer:
    def __init__(self, features):
        self._features = features

    def getFeatures(self):
        return iter(self._features)


class _FakeFuture:
    def __init__(self, result):
        self._result = result

    def result(self):
        return self._result


class _FakeExecutor:
    instances = []

    def __init__(self, max_workers, mp_context):
        self.max_workers = max_workers
        self.mp_context = mp_context
        self.submissions = []
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def submit(self, runner, **kwargs):
        self.submissions.append((runner, kwargs))
        fsa = kwargs['fsa']
        return _FakeFuture(FsaBatchItemResult(
            fsa=fsa, succeeded=True, standardized_artifact_id=f'artifact-{fsa}'))


class TestFsaBatchRunner(unittest.TestCase):
    def test_normalize_fsas_preserves_order_and_removes_duplicates(self):
        self.assertEqual(
            normalize_fsas([' h3h ', 'H2X', 'h3h']),
            ('H3H', 'H2X'))

    @patch.object(fsa_batch_runner, 'discover_component_fsas')
    def test_explicit_fsas_run_arbitrary_component_without_discovery(
            self,
            discover_mock):
        component_runner = Mock(
            return_value=_ComponentResult('future_H3H.gpkg'))

        result = run_fsa_batch(
            component_name='future_fsa_gisoo',
            fsas=['h3h'],
            mode='standardize',
            component_runner=component_runner)

        self.assertTrue(result.succeeded)
        self.assertEqual(result.component_name, 'future_fsa_gisoo')
        self.assertEqual(result.fsas, ('H3H',))
        discover_mock.assert_not_called()
        component_runner.assert_called_once_with(
            component_name='future_fsa_gisoo',
            mode='standardize',
            fsa='H3H',
            non_null_required_fields=None)

    def test_discover_component_fsas_uses_selected_workflow_config(self):
        workflow_config = types.SimpleNamespace(
            qgis_path='C:/QGIS',
            input_paths={'fsa': 'future_fsas.gpkg'},
            fsa_field_name='district')
        scrub_layer = Mock()
        scrub_layer.layer = _FeatureLayer([
            {'district': 'h3h'},
            {'district': 'H2X'},
            {'district': 'H3H'},
            {'district': None},
        ])
        scrub_layer_class = Mock(return_value=scrub_layer)
        scrub_layer_module = types.ModuleType('citygisoo.scrub_layer_class')
        scrub_layer_module.ScrubLayer = scrub_layer_class
        citygisoo_module = types.ModuleType('citygisoo')

        with patch.object(
                fsa_batch_runner,
                '_load_fsa_discovery_config',
                return_value=workflow_config):
            with patch.dict(
                    sys.modules,
                    {
                        'citygisoo': citygisoo_module,
                        'citygisoo.scrub_layer_class': scrub_layer_module,
                    }):
                result = discover_component_fsas('future_fsa_gisoo')

        self.assertEqual(result, ('H2X', 'H3H'))
        scrub_layer_class.assert_called_once_with(
            'C:/QGIS',
            'future_fsas.gpkg',
            'future_fsa_gisoo_fsa_boundaries')

    @patch.object(fsa_batch_runner.importlib, 'import_module')
    def test_discovery_config_reports_missing_standard_fields(
            self,
            import_module_mock):
        import_module_mock.return_value = types.SimpleNamespace(
            qgis_path='C:/QGIS')

        with self.assertRaisesRegex(
                GisComponentContractError,
                'input_paths, fsa_field_name'):
            fsa_batch_runner._load_fsa_discovery_config(
                'future_fsa_gisoo')

    def test_component_capability_requires_fsa_parameter(self):
        with patch.object(
                fsa_batch_runner.GISCitiesApplicationService,
                '_normalize_component_name',
                return_value='future_fsa_gisoo'):
            with patch.object(
                    fsa_batch_runner.GISCitiesApplicationService,
                    '_ensure_component_callable'):
                with patch.object(
                        fsa_batch_runner.GISCitiesApplicationService,
                        '_import_component_callable',
                        return_value=lambda: None):
                    with self.assertRaisesRegex(
                            GisComponentContractError,
                            'must accept an fsa parameter'):
                        fsa_batch_runner._ensure_fsa_component(
                            'future_fsa_gisoo')

    def test_cleanup_and_retained_outputs_are_forwarded(self):
        component_runner = Mock(
            return_value=_ComponentResult(
                'future_H3H.gpkg',
                cleaned_output_paths=('deleted.gpkg',)))
        runner = FsaBatchRunner(
            component_name='future_fsa_gisoo',
            cleanup_outputs=True,
            keep_outputs=['usage_clean', 'inter_summary'],
            component_runner=component_runner)

        result = runner.run_fsas(['h3h'])

        self.assertEqual(
            result.results[0].cleaned_output_paths,
            ('deleted.gpkg',))
        component_runner.assert_called_once_with(
            component_name='future_fsa_gisoo',
            mode='standardize',
            fsa='H3H',
            non_null_required_fields=None,
            cleanup_outputs=True,
            keep_outputs=('usage_clean', 'inter_summary'))

    def test_failure_is_recorded_and_remaining_fsas_continue(self):
        component_runner = Mock(side_effect=[
            RuntimeError('boom'),
            _ComponentResult('future_H2X.gpkg', standardized_artifact_id='a' * 32),
        ])

        result = run_fsa_batch(
            component_name='future_fsa_gisoo',
            fsas=['H3H', 'H2X'],
            component_runner=component_runner)

        self.assertEqual(result.succeeded_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.assertIn('RuntimeError: boom', result.results[0].error)
        self.assertTrue(result.results[1].succeeded)
        self.assertIsNone(result.results[0].standardized_artifact_id)
        self.assertEqual(result.results[1].standardized_artifact_id, 'a' * 32)

    def test_three_worker_parallel_results_keep_fsa_order(self):
        _FakeExecutor.instances = []
        spawn_context = object()
        with patch.object(
                fsa_batch_runner.multiprocessing,
                'get_context',
                return_value=spawn_context):
            with patch.object(
                    fsa_batch_runner,
                    'ProcessPoolExecutor',
                    _FakeExecutor):
                with patch.object(
                        fsa_batch_runner,
                        'as_completed',
                        side_effect=lambda futures: reversed(list(futures))):
                    results = fsa_batch_runner._run_fsa_batch_parallel(
                        component_name='future_fsa_gisoo',
                        fsas=('H3H', 'H2X', 'H1A'),
                        mode='standardize',
                        non_null_required_fields=None,
                        cleanup_outputs=True,
                        keep_outputs=('usage_clean',),
                        max_workers=3,
                        result_callback=None)

        self.assertEqual(
            tuple(result.fsa for result in results),
            ('H3H', 'H2X', 'H1A'))
        self.assertEqual(
            tuple(result.standardized_artifact_id for result in results),
            ('artifact-H3H', 'artifact-H2X', 'artifact-H1A'))
        executor = _FakeExecutor.instances[0]
        self.assertEqual(executor.max_workers, 3)
        self.assertIs(executor.mp_context, spawn_context)
        self.assertEqual(len(executor.submissions), 3)


if __name__ == '__main__':
    unittest.main()
