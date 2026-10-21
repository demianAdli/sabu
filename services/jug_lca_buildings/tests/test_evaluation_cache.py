"""Verify explicit evaluation provenance and filesystem cache boundaries."""

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from datetime import datetime
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.jug_lca_buildings import evaluation_cache as preparation


def configuration(label='baseline'):
    return {
        'configuration_label': label,
        'source_revision': 'source-snapshot-1',
        'local_changes': 'none',
        'reference_data': {name: 'reference-snapshot-1'
                           for name in preparation.REFERENCE_DATA},
        'calculation_settings': {},
    }


def snapshot(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob('*') if path.is_file()}


class TestEvaluationPreparation(unittest.TestCase):
    def setUp(self):
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.cache = self.root / 'cache'
        self.context.enter_context(patch.dict(os.environ, {
            'JUG_LCA_ARTIFACTS_DIR': str(self.cache),
        }))
        self.distributions = self.context.enter_context(patch.object(
            preparation.metadata, 'distributions', return_value=[
                SimpleNamespace(metadata={'Name': 'cerc-hub'}, version='0.2.0.8'),
                SimpleNamespace(metadata={'Name': 'jug_lca_buildings'}, version='0.1.1'),
            ],
        ))

    def test_manifest_records_configuration_environment_and_cache_location(self):
        declared = configuration()
        path = preparation.prepare_evaluation_cache(declared)
        manifest = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(manifest['configuration'], declared)
        self.assertEqual(manifest['cache_directory'], str(self.cache.resolve()))
        self.assertEqual(manifest['cache_namespace'],
                         preparation.EmissionsArtifactStore.CACHE_NAMESPACE)
        self.assertEqual(manifest['software_environment']['installed_distributions'], [
            {'name': 'cerc-hub', 'version': '0.2.0.8'},
            {'name': 'jug_lca_buildings', 'version': '0.1.1'},
        ])
        self.assertTrue(manifest['software_environment']['python_version'])
        self.assertTrue(manifest['software_environment']['platform'])
        self.assertIsNotNone(datetime.fromisoformat(manifest['created_at_utc']).tzinfo)

    def test_reuse_requires_opt_in_and_preserves_manifest_and_artifacts(self):
        declared = configuration()
        path = preparation.prepare_evaluation_cache(declared)
        (self.cache / 'old-result.json').write_text('preserve me', encoding='utf-8')
        original = snapshot(self.cache)
        with self.assertRaisesRegex(ValueError, '--reuse'):
            preparation.prepare_evaluation_cache(declared)
        self.assertEqual(preparation.prepare_evaluation_cache(declared, reuse=True), path)
        self.assertEqual(snapshot(self.cache), original)

    def test_changed_provenance_cannot_relabel_existing_results(self):
        declared = configuration()
        preparation.prepare_evaluation_cache(declared)
        original = snapshot(self.cache)
        for field, value in (
            ('source_revision', 'source-snapshot-2'),
            ('local_changes', 'saved-patch-2'),
            ('reference_data', {name: 'reference-snapshot-2'
                                for name in preparation.REFERENCE_DATA}),
            ('calculation_settings', {'catalog': 'different'}),
        ):
            changed = deepcopy(declared)
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'differs'):
                preparation.prepare_evaluation_cache(changed, reuse=True)
        self.distributions.return_value = [
            SimpleNamespace(metadata={'Name': 'cerc-hub'}, version='changed'),
        ]
        with self.assertRaisesRegex(ValueError, 'differs'):
            preparation.prepare_evaluation_cache(declared, reuse=True)
        self.assertEqual(snapshot(self.cache), original)

    def test_legacy_files_are_never_adopted_or_changed(self):
        self.cache.mkdir()
        (self.cache / 'emissions.json').write_text('[{"old": true}]', encoding='utf-8')
        original = snapshot(self.cache)
        for reuse in (False, True):
            with self.subTest(reuse=reuse), self.assertRaises(ValueError):
                preparation.prepare_evaluation_cache(configuration(), reuse=reuse)
            self.assertEqual(snapshot(self.cache), original)

    def test_malformed_manifest_is_preserved_and_rejected(self):
        self.cache.mkdir()
        path = self.cache / preparation.MANIFEST_NAME
        for content in ('{broken', '[]'):
            path.write_text(content, encoding='utf-8')
            with self.subTest(content=content), self.assertRaises(ValueError):
                preparation.prepare_evaluation_cache(configuration(), reuse=True)
            self.assertEqual(path.read_text(encoding='utf-8'), content)

    def test_namespace_changes_require_another_directory(self):
        preparation.prepare_evaluation_cache(configuration())
        original = snapshot(self.cache)
        with patch.object(preparation.EmissionsArtifactStore, 'CACHE_NAMESPACE', 'future'):
            with self.assertRaisesRegex(ValueError, 'differs'):
                preparation.prepare_evaluation_cache(configuration(), reuse=True)
        self.assertEqual(snapshot(self.cache), original)

    def test_configuration_and_explicit_directory_required_before_creation(self):
        for invalid in ([], {}, dict(configuration(), reference_data={}),
                        dict(configuration(), source_revision=' '),
                        dict(configuration(), calculation_settings=None)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                preparation.prepare_evaluation_cache(invalid)
        with patch.dict(os.environ, {'JUG_LCA_ARTIFACTS_DIR': ''}):
            with self.assertRaisesRegex(ValueError, 'explicitly'):
                preparation.prepare_evaluation_cache(configuration())
        self.assertFalse(self.cache.exists())

    def test_command_prepares_and_verifies_without_rewriting_manifest(self):
        source = self.root / 'configuration.json'
        source.write_text(json.dumps(configuration()), encoding='utf-8')
        with redirect_stdout(io.StringIO()) as output:
            preparation.main(['--configuration', str(source)])
        path = self.cache / preparation.MANIFEST_NAME
        self.assertEqual(output.getvalue().strip(), str(path.resolve()))
        original = snapshot(self.cache)
        with redirect_stdout(io.StringIO()):
            preparation.main(['--configuration', str(source), '--reuse'])
        self.assertEqual(snapshot(self.cache), original)


class TestEvaluationCacheIsolation(unittest.TestCase):
    def setUp(self):
        # Keep preparation tests usable without the calculation dependencies.
        from src.jug_lca_buildings.application import EmissionsApplicationService
        from tests.test_emissions_api import _build_test_app
        from tests.test_input_validation import valid_city, city_with_metadata

        self.service = EmissionsApplicationService
        self.city = valid_city()
        self.equivalent_city = city_with_metadata()
        self.client = _build_test_app().test_client()
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.application = 'src.jug_lca_buildings.application.jug_lca_buildings'
        self.workflow = self.context.enter_context(patch(
            f'{self.application}.LCACarbonWorkflow'))

    def test_configurations_isolate_results_and_csv_then_reuse_each_directory(self):
        results = []
        for label, value in (('A', 3.0), ('B', 99.0)):
            cache = self.root / label
            declared = configuration(label)
            declared['source_revision'] = f'calculation-{label}'
            with patch.dict(os.environ, {'JUG_LCA_ARTIFACTS_DIR': str(cache)}):
                manifest = preparation.prepare_evaluation_cache(declared)
                self.workflow.return_value.export_emissions.return_value = [
                    {'component_embodied_emissions': value}]
                with self.assertLogs(self.application, level='INFO') as logs:
                    result = self.service.compute_emissions(self.city)
                    report = self.service.build_csv_report(self.city, result)
                self.assertFalse(result.cache_hit)
                self.assertFalse(report['cache_hit'])
                self.assertEqual([record.artifact_kind for record in logs.records],
                                 ['emissions', 'csv_report'])
                for record in logs.records:
                    self.assertEqual(record.request_hash, result.request_hash)
                    self.assertEqual(len(record.request_hash), 64)
                    self.assertEqual(record.cache_directory, str(cache.resolve()))
                    self.assertFalse(record.cache_hit)
                before_reuse = snapshot(cache)
                preparation.prepare_evaluation_cache(declared, reuse=True)
                # API requests share the cache populated by direct invocation.
                with self.assertLogs(self.application, level='INFO') as hit_logs:
                    response = self.client.post('/emissions', json=self.equivalent_city)
                    csv_response = self.client.post('/emissions?export=csv', json=self.city)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.get_json(), result.emissions_data)
                self.assertEqual(csv_response.status_code, 200)
                stored_csv = cache / result.request_hash / 'emissions_report.csv'
                self.assertEqual(csv_response.get_data(as_text=True),
                                 stored_csv.read_text(encoding='utf-8'))
                self.assertTrue(all(record.cache_hit for record in hit_logs.records))
                self.assertTrue(all(record.request_hash == result.request_hash
                                    and record.cache_directory == str(cache.resolve())
                                    for record in hit_logs.records))
                self.assertEqual(snapshot(cache), before_reuse)
                self.assertEqual(json.loads(manifest.read_text(encoding='utf-8'))[
                    'configuration']['source_revision'], f'calculation-{label}')
                results.append((result, report))
        self.assertEqual(self.workflow.call_count, 2)
        self.assertEqual(results[0][0].request_hash, results[1][0].request_hash)
        self.assertNotEqual(results[0][0].emissions_data, results[1][0].emissions_data)
        self.assertNotEqual(results[0][1]['csv_text'], results[1][1]['csv_text'])
        # Returning to A after running B still returns A's original result.
        with patch.dict(os.environ, {'JUG_LCA_ARTIFACTS_DIR': str(self.root / 'A')}):
            reused = self.service.compute_emissions(self.city)
        self.assertTrue(reused.cache_hit)
        self.assertEqual(reused.emissions_data, results[0][0].emissions_data)
        self.assertEqual(self.workflow.call_count, 2)
