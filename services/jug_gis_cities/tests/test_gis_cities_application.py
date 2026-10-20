"""
Sabu project
jug_gis_cities package
test_gis_cities_application module
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import unittest
import os
import sys
import types
from unittest.mock import Mock, call, patch


_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_SABU_CHASSIS_SRC = os.path.join(_REPO_ROOT, 'libs', 'sabu_chassis', 'src')
if _SABU_CHASSIS_SRC not in sys.path:
    sys.path.insert(0, _SABU_CHASSIS_SRC)

from src.jug_gis_cities.application.jug_gis_cities import (
    _execute_component_worker,
    _initialize_worker_qgis,
    _run_component_in_fresh_process,
    _shutdown_worker_qgis,
    GisComponentCleanupError,
    GisComponentContractError,
    GisComponentError,
    GisComponentRunMode,
    GisComponentRunResult,
    GISCitiesApplicationService,
)
from src.jug_gis_cities.application.artifacts import ArtifactError


class TestGISCitiesApplicationService(unittest.TestCase):
    def setUp(self):
        patcher = patch(
            'src.jug_gis_cities.application.jug_gis_cities.get_artifact_store')
        self.artifact_store = patcher.start().return_value
        self.artifact_store.register.return_value.artifact_id = 'a' * 32
        self.addCleanup(patcher.stop)

    def test_worker_shutdown_releases_project_layers_and_exits_qgis(self):
        qgis_application = Mock()
        project = Mock()
        fake_qgis = types.ModuleType('qgis')
        fake_qgis_core = types.ModuleType('qgis.core')
        fake_qgis_core.QgsApplication = Mock()
        fake_qgis_core.QgsProject = Mock()
        fake_qgis_core.QgsProject.instance.return_value = project

        with patch.dict(
                sys.modules,
                {'qgis': fake_qgis, 'qgis.core': fake_qgis_core}):
            _shutdown_worker_qgis(qgis_application)

        project.removeAllMapLayers.assert_called_once_with()
        qgis_application.exitQgis.assert_called_once_with()

    def test_worker_qgis_initialization_uses_configured_environment_prefix(self):
        class _FakeQgsApplication:
            configured_prefix = None
            initialized = False

            @classmethod
            def instance(cls):
                return None

            @classmethod
            def setPrefixPath(cls, prefix, use_default_paths):
                cls.configured_prefix = (prefix, use_default_paths)

            @classmethod
            def prefixPath(cls):
                return cls.configured_prefix[0]

            def __init__(self, argv, gui_enabled):
                self.argv = argv
                self.gui_enabled = gui_enabled

            def initQgis(self):
                type(self).initialized = True

        fake_qgis = types.ModuleType('qgis')
        fake_qgis_core = types.ModuleType('qgis.core')
        fake_qgis_core.QgsApplication = _FakeQgsApplication
        with patch.dict(
                sys.modules,
                {'qgis': fake_qgis, 'qgis.core': fake_qgis_core}):
            with patch.dict(
                    os.environ,
                    {'JUG_GIS_CITIES_QGIS_PATH': 'C:/QGIS44'}):
                qgis_application = _initialize_worker_qgis()

        self.assertEqual(
            _FakeQgsApplication.configured_prefix,
            ('C:/QGIS44', True))
        self.assertTrue(_FakeQgsApplication.initialized)
        self.assertEqual(qgis_application.argv, [])
        self.assertFalse(qgis_application.gui_enabled)

    @patch(
        'src.jug_gis_cities.application.jug_gis_cities.'
        'ProcessPoolExecutor'
    )
    @patch(
        'src.jug_gis_cities.application.jug_gis_cities.'
        'multiprocessing.get_context'
    )
    def test_fresh_process_runner_uses_spawn_and_waits_for_result(
            self,
            get_context_mock,
            executor_class_mock):
        spawn_context = object()
        get_context_mock.return_value = spawn_context
        executor = executor_class_mock.return_value.__enter__.return_value
        executor.submit.return_value.result.return_value = 'worker-result'

        result = _run_component_in_fresh_process(
            component_name='mtl_fsa_gisoo',
            mode='standardize',
            fsa='H3H',
            non_null_required_fields=['FSA'])

        self.assertEqual(result, 'worker-result')
        get_context_mock.assert_called_once_with('spawn')
        executor_class_mock.assert_called_once_with(
            max_workers=1,
            mp_context=spawn_context)
        executor.submit.assert_called_once_with(
            _execute_component_worker,
            'mtl_fsa_gisoo',
            'standardize',
            'H3H',
            ['FSA'])

    def test_normalize_mode_accepts_strings_and_enum(self):
        self.assertEqual(
            GISCitiesApplicationService._normalize_mode(' STANDARDIZE '),
            GisComponentRunMode.STANDARDIZE)
        self.assertEqual(
            GISCitiesApplicationService._normalize_mode(
                GisComponentRunMode.INDEPENDENT),
            GisComponentRunMode.INDEPENDENT)

    def test_normalize_mode_rejects_unsupported_mode(self):
        with self.assertRaises(ValueError):
            GISCitiesApplicationService._normalize_mode('finalize')

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    def test_run_component_independent_runs_workflow_only(
            self,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'saint_malachie_gisoo'
        workflow_runner = Mock(return_value='workflow_output.shp')
        import_component_callable_mock.return_value = workflow_runner

        result = GISCitiesApplicationService.run_component(
            ' saint_malachie_gisoo ',
            mode='independent')

        self.assertEqual(result.component_name, 'saint_malachie_gisoo')
        self.assertEqual(result.mode, GisComponentRunMode.INDEPENDENT)
        self.assertEqual(result.workflow_output_path, 'workflow_output.shp')
        self.assertIsNone(result.fsa)
        self.assertIsNone(result.standardized_output_path)
        self.assertIsNone(result.standardized_artifact_id)
        self.artifact_store.register.assert_not_called()
        ensure_component_callable_mock.assert_called_once_with(
            component_name='saint_malachie_gisoo',
            module_name='workflow',
            callable_name='run_workflow')
        import_component_callable_mock.assert_called_once_with(
            component_name='saint_malachie_gisoo',
            module_name='workflow',
            callable_name='run_workflow')
        workflow_runner.assert_called_once_with()

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    def test_run_component_standardize_runs_workflow_and_contract_adapter(
            self,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'saint_malachie_gisoo'
        workflow_runner = Mock(return_value='workflow_output.shp')
        contract_adapter_runner = Mock(return_value='standardized.geojson')
        import_component_callable_mock.side_effect = [
            workflow_runner,
            contract_adapter_runner,
        ]

        result = GISCitiesApplicationService.run_component(
            'saint_malachie_gisoo',
            mode='standardize')

        self.assertEqual(result.component_name, 'saint_malachie_gisoo')
        self.assertEqual(result.mode, GisComponentRunMode.STANDARDIZE)
        self.assertEqual(result.workflow_output_path, 'workflow_output.shp')
        self.assertIsNone(result.fsa)
        self.assertEqual(
            result.standardized_output_path,
            'standardized.geojson')
        ensure_component_callable_mock.assert_has_calls([
            call(
                component_name='saint_malachie_gisoo',
                module_name='workflow',
                callable_name='run_workflow'),
            call(
                component_name='saint_malachie_gisoo',
                module_name='contract_adapter',
                callable_name='run_contract_adapter'),
        ])
        workflow_runner.assert_called_once_with()
        contract_adapter_runner.assert_called_once_with()
        self.assertEqual(result.standardized_artifact_id, 'a' * 32)
        self.artifact_store.register.assert_called_once_with(
            'standardized.geojson', component_name='saint_malachie_gisoo', fsa=None)

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    def test_run_component_passes_normalized_fsa_to_supported_callables(
            self,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'mtl_fsa_gisoo'
        calls = []

        def workflow_runner(*, fsa):
            calls.append(('workflow', fsa))
            return f'workflow_{fsa}.shp'

        def contract_adapter_runner(*, fsa):
            calls.append(('contract_adapter', fsa))
            return f'standardized_{fsa}.geojson'

        import_component_callable_mock.side_effect = [
            workflow_runner,
            contract_adapter_runner,
        ]

        result = GISCitiesApplicationService.run_component(
            'mtl_fsa_gisoo',
            mode='standardize',
            fsa=' h3h ')

        self.assertEqual(result.fsa, 'H3H')
        self.assertEqual(result.workflow_output_path, 'workflow_H3H.shp')
        self.assertEqual(
            result.standardized_output_path,
            'standardized_H3H.geojson')
        self.assertEqual(
            calls,
            [('workflow', 'H3H'), ('contract_adapter', 'H3H')])

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    def test_run_component_passes_optional_non_null_fields_to_adapter(
            self,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'mtl_fsa_gisoo'
        calls = []

        def workflow_runner(*, fsa):
            calls.append(('workflow', fsa))
            return f'workflow_{fsa}.gpkg'

        def contract_adapter_runner(*, fsa, non_null_required_fields=None):
            calls.append(
                ('contract_adapter', fsa, non_null_required_fields))
            return f'standardized_{fsa}.geojson'

        import_component_callable_mock.side_effect = [
            workflow_runner,
            contract_adapter_runner,
        ]

        result = GISCitiesApplicationService.run_component(
            'mtl_fsa_gisoo',
            mode='standardize',
            fsa='h3h',
            non_null_required_fields=['citygisoo_id', 'FSA'])

        self.assertEqual(
            result.standardized_output_path,
            'standardized_H3H.geojson')
        self.assertEqual(
            calls,
            [
                ('workflow', 'H3H'),
                ('contract_adapter', 'H3H', ['citygisoo_id', 'FSA']),
            ])

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    def test_run_component_omits_non_null_fields_for_unsupported_adapter(
            self,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'mtl_fsa_gisoo'
        calls = []

        def workflow_runner(*, fsa):
            return f'workflow_{fsa}.gpkg'

        def contract_adapter_runner(*, fsa):
            calls.append(('contract_adapter', fsa))
            return f'standardized_{fsa}.geojson'

        import_component_callable_mock.side_effect = [
            workflow_runner,
            contract_adapter_runner,
        ]

        GISCitiesApplicationService.run_component(
            'mtl_fsa_gisoo',
            mode='standardize',
            fsa='h3h',
            non_null_required_fields=['citygisoo_id'])

        self.assertEqual(calls, [('contract_adapter', 'H3H')])

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    def test_run_component_requires_fsa_when_workflow_requires_it(
            self,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'mtl_fsa_gisoo'

        def workflow_runner(*, fsa):
            return f'workflow_{fsa}.shp'

        import_component_callable_mock.return_value = workflow_runner

        with self.assertRaises(ValueError):
            GISCitiesApplicationService.run_component(
                'mtl_fsa_gisoo',
                mode='independent')

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    def test_run_component_rejects_fsa_for_unsupported_workflow(
            self,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'saint_malachie_gisoo'

        def workflow_runner():
            return 'workflow_output.shp'

        import_component_callable_mock.return_value = workflow_runner

        with self.assertRaises(ValueError):
            GISCitiesApplicationService.run_component(
                'saint_malachie_gisoo',
                mode='independent',
                fsa='H3H')

    def test_standardize_requires_component_contract_adapter(self):
        with patch.object(
                GISCitiesApplicationService,
                '_PACKAGE_NAME',
                'src.jug_gis_cities'):
            with self.assertRaises(GisComponentContractError):
                GISCitiesApplicationService._ensure_component_callable(
                    component_name='mtl_gisoo',
                    module_name='contract_adapter',
                    callable_name='run_contract_adapter')

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    def test_run_component_wraps_workflow_exceptions(
            self,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'saint_malachie_gisoo'
        workflow_runner = Mock(side_effect=RuntimeError('boom'))
        import_component_callable_mock.return_value = workflow_runner

        with self.assertRaises(GisComponentError):
            GISCitiesApplicationService.run_component(
                'saint_malachie_gisoo',
                mode='independent')

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    @patch(
        'src.jug_gis_cities.application.jug_gis_cities.'
        '_run_component_in_fresh_process'
    )
    def test_run_component_cleans_only_after_standardization(
            self,
            fresh_process_mock,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'mtl_fsa_gisoo'
        calls = []

        def cleanup_runner(
                *, fsa, keep_outputs=None, validate_only=False):
            calls.append(
                ('cleanup', fsa, keep_outputs, validate_only))
            if validate_only:
                return ()
            return ('deleted_output',)

        import_component_callable_mock.return_value = cleanup_runner
        fresh_process_mock.side_effect = lambda **kwargs: (
            calls.append(('worker', kwargs)) or GisComponentRunResult(
                component_name='mtl_fsa_gisoo',
                mode=GisComponentRunMode.STANDARDIZE,
                fsa='H3H',
                workflow_output_path='workflow_H3H.gpkg',
                standardized_output_path='standardized_H3H.geojson',
                standardized_artifact_id='b' * 32))

        result = GISCitiesApplicationService.run_component(
            'mtl_fsa_gisoo',
            mode='standardize',
            fsa='h3h',
            cleanup_outputs=True,
            keep_outputs=['usage_clean'])

        self.assertEqual(result.cleaned_output_paths, ('deleted_output',))
        self.assertEqual(result.standardized_artifact_id, 'b' * 32)
        self.artifact_store.register.assert_not_called()
        self.assertEqual(calls, [
            ('cleanup', 'H3H', ['usage_clean'], True),
            ('worker', {
                'component_name': 'mtl_fsa_gisoo',
                'mode': 'standardize',
                'fsa': 'H3H',
                'non_null_required_fields': None,
            }),
            ('cleanup', 'H3H', ['usage_clean'], False),
        ])
        ensure_component_callable_mock.assert_called_once_with(
            component_name='mtl_fsa_gisoo',
            module_name='output_cleanup',
            callable_name='cleanup_outputs')

    @patch.object(GISCitiesApplicationService, '_import_component_callable')
    @patch.object(GISCitiesApplicationService, '_ensure_component_callable')
    @patch.object(GISCitiesApplicationService, '_normalize_component_name')
    @patch(
        'src.jug_gis_cities.application.jug_gis_cities.'
        '_run_component_in_fresh_process'
    )
    def test_isolated_cleanup_failure_preserves_successful_output_context(
            self,
            fresh_process_mock,
            normalize_component_name_mock,
            ensure_component_callable_mock,
            import_component_callable_mock):
        normalize_component_name_mock.return_value = 'mtl_fsa_gisoo'

        def cleanup_runner(*, fsa, keep_outputs=None, validate_only=False):
            if validate_only:
                return ()
            raise PermissionError('locked')

        import_component_callable_mock.return_value = cleanup_runner
        fresh_process_mock.return_value = GisComponentRunResult(
            component_name='mtl_fsa_gisoo',
            mode=GisComponentRunMode.STANDARDIZE,
            fsa='H3H',
            workflow_output_path='workflow_H3H.gpkg',
            standardized_output_path='standardized_H3H.geojson')

        with self.assertRaisesRegex(
                GisComponentCleanupError,
                'outputs were created'):
            GISCitiesApplicationService.run_component(
                'mtl_fsa_gisoo',
                mode='standardize',
                fsa='H3H',
                cleanup_outputs=True)

    def test_keep_outputs_requires_cleanup(self):
        with patch.object(
                GISCitiesApplicationService,
                '_normalize_component_name',
                return_value='mtl_fsa_gisoo'):
            with self.assertRaises(ValueError):
                GISCitiesApplicationService.run_component(
                    'mtl_fsa_gisoo',
                    mode='independent',
                    fsa='H3H',
                    keep_outputs=['usage_clean'])

    def test_registration_failure_fails_component_run(self):
        self.artifact_store.register.side_effect = ArtifactError('disk full')
        with patch.object(GISCitiesApplicationService, '_normalize_component_name',
                          return_value='saint_malachie_gisoo'), \
                patch.object(GISCitiesApplicationService, '_ensure_component_callable'), \
                patch.object(GISCitiesApplicationService, '_import_component_callable',
                             side_effect=[Mock(return_value='raw.shp'),
                                          Mock(return_value='standardized.geojson')]):
            with self.assertRaisesRegex(GisComponentError, 'register standardized'):
                GISCitiesApplicationService.run_component('saint_malachie_gisoo')


if __name__ == '__main__':
    unittest.main()
