"""
Sabu project
jug_sim_buildings package
test_feature_identity module
Verify LCA reader identity reconciliation without positional assumptions.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.jug_lca_buildings.lca_carbon_workflow import LCACarbonWorkflow
from src.jug_lca_buildings.storage import EmissionsArtifactStore


class TestFeatureIdentity(unittest.TestCase):
    def workflow(self, names):
        workflow = object.__new__(LCACarbonWorkflow)
        workflow.city = SimpleNamespace(buildings=[SimpleNamespace(name=name) for name in names])
        workflow.submitted_feature_ids = {'3': 3, '8': 8}
        return workflow

    def test_shuffled_reader_buildings_keep_verified_source_ids(self):
        workflow = self.workflow(['8', '3'])
        self.assertEqual(workflow._reader_feature_ids(), [8, 3])
        workflow.calculate_building_component_emission = lambda building: (1, 2, 3, 4, 5, 9)
        workflow.progress_log_every = 100
        for key in ('envelope_emission', 'opening_emission', 'component_emission',
                    'envelope_end_of_life_emission', 'opening_end_of_life_emission',
                    'component_end_of_life_emission'):
            setattr(workflow, 'building_' + key, [])
        payload = workflow.export_emissions()
        self.assertEqual([row['feature_id'] for row in payload], [8, 3])
        self.assertEqual(payload[0]['component_end_of_life_emissions'], 9)

    def test_omitted_duplicated_or_unexpected_reader_identity_fails(self):
        for names in (['3'], ['3', '3'], ['3', '9']):
            with self.subTest(names=names), self.assertRaisesRegex(ValueError, 'reader identity mismatch'):
                self.workflow(names)._reader_feature_ids()

    def test_real_small_footprint_omission_fails_before_enrichment(self):
        city = {'type': 'FeatureCollection', 'features': [{
            'type': 'Feature', 'id': 3, 'properties': {
                'name': 'H3B_3', 'height': 10, 'function': '1000', 'year_of_construction': 1980,
                'address': 'test'}, 'geometry': {'type': 'Polygon', 'coordinates': [[
                    [-73.6, 45.5], [-73.59999, 45.5], [-73.59999, 45.50001],
                    [-73.6, 45.50001], [-73.6, 45.5]]]}}]}
        with TemporaryDirectory() as root:
            path = Path(root) / 'H3B.geojson'
            path.write_text(json.dumps(city), encoding='utf-8')
            with patch('src.jug_lca_buildings.lca_carbon_workflow.ConstructionFactory') as factory:
                with self.assertRaisesRegex(ValueError, "missing=\\['3'\\]"):
                    LCACarbonWorkflow(str(path), 'nrcan_archetypes.json', 'nrcan_constructions_cap_3.json')
                factory.assert_not_called()

    def test_api_preserves_result_feature_id_and_new_cache_namespace(self):
        from tests.test_emissions_api import TestEmissionsApi
        fixture = TestEmissionsApi()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        results = [{**fixture.workflow_result[0], 'feature_id': 1}]
        with patch('src.jug_lca_buildings.application.jug_lca_buildings.LCACarbonWorkflow') as workflow:
            workflow.return_value.export_emissions.return_value = results
            response = fixture.client.post('/emissions', json=fixture.valid_payload)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.get_json(), results)
            fixture.client.post('/emissions', json=fixture.valid_payload)
            self.assertEqual(workflow.call_count, 1)
        self.assertEqual(EmissionsArtifactStore.CACHE_NAMESPACE, 'jug_lca_buildings_emissions_v3_identified')
