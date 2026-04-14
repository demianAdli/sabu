import io
import json
import os
import tempfile
import unittest
import csv
from unittest.mock import patch

from flask import Flask
from flask_smorest import Api

from src.jug_lca_buildings.resources.emissions import (
    blp as emissions_blueprint,
)
from src.jug_lca_buildings.reporting import EmissionsReportExporter


def _build_test_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['PROPAGATE_EXCEPTIONS'] = True
    app.config['API_TITLE'] = 'LCA Carbon Workflow API'
    app.config['API_VERSION'] = 'v1'
    app.config['OPENAPI_VERSION'] = '3.0.2'

    api = Api(app)
    api.register_blueprint(emissions_blueprint)
    return app


class TestEmissionsApi(unittest.TestCase):
    def setUp(self):
        self._artifacts_tmpdir = tempfile.TemporaryDirectory()
        self._env_patcher = patch.dict(
            os.environ,
            {'JUG_LCA_ARTIFACTS_DIR': self._artifacts_tmpdir.name},
        )
        self._env_patcher.start()
        self.app = _build_test_app()
        self.client = self.app.test_client()
        self.valid_payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": 1,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-73.57, 45.5],
                                [-73.56, 45.5],
                                [-73.56, 45.51],
                                [-73.57, 45.5]
                            ]
                        ]
                    },
                    "properties": {
                        "name": "Building 1",
                        "address": "123 Test St",
                        "function": "Residential",
                        "height": 12.5,
                        "year_of_construction": 1995
                    }
                }
            ]
        }
        self.workflow_result = [
            {
                'opening_embodied_emissions': 1.0,
                'envelope_embodied_emissions': 2.0,
                'component_embodied_emissions': 3.0,
                'opening_end_of_life_emissions': 4.0,
                'envelope_end_of_life_emissions': 5.0,
                'component_end_of_life_emissions': 6.0
            }
        ]

    def tearDown(self):
        self._env_patcher.stop()
        self._artifacts_tmpdir.cleanup()

    @patch(
        'src.jug_lca_buildings.application.jug_lca_buildings.LCACarbonWorkflow'
    )
    def test_post_emissions_json_contract(self, workflow_cls_mock):
        workflow_cls_mock.return_value.export_emissions.return_value = (
            self.workflow_result
        )

        response = self.client.post('/emissions', json=self.valid_payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), self.workflow_result)
        workflow_cls_mock.assert_called_once_with(
            self.valid_payload,
            'nrcan_archetypes.json',
            'nrcan_constructions_cap_3.json'
        )

    @patch(
        'src.jug_lca_buildings.application.jug_lca_buildings.LCACarbonWorkflow'
    )
    def test_post_emissions_csv_export_contract(self, workflow_cls_mock):
        workflow_cls_mock.return_value.export_emissions.return_value = (
            self.workflow_result
        )

        response = self.client.post(
            '/emissions?export=csv',
            json=self.valid_payload
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertIn(
            'attachment; filename=',
            response.headers.get('Content-Disposition', ''),
        )
        csv_body = response.get_data(as_text=True)
        self.assertIn(
            'building_index,feature_id,name,address,function',
            csv_body,
        )
        self.assertIn('opening_embodied_emissions_kgco2e', csv_body)
        self.assertIn('TOTAL', csv_body)
        self.assertIn('Building 1', csv_body)

    def test_csv_report_totals_do_not_double_count_component_values(self):
        csv_text = EmissionsReportExporter.build_csv_text(
            self.valid_payload,
            self.workflow_result,
        )

        rows = list(csv.DictReader(io.StringIO(csv_text)))

        self.assertEqual(len(rows), 2)

        building_row = rows[0]
        self.assertEqual(
            float(building_row['total_embodied_emissions_kgco2e']),
            3.0,
        )
        self.assertEqual(
            float(building_row['total_end_of_life_emissions_kgco2e']),
            6.0,
        )
        self.assertEqual(
            float(building_row['total_lca_emissions_kgco2e']),
            9.0,
        )

        total_row = rows[1]
        self.assertEqual(total_row['feature_id'], 'TOTAL')
        self.assertEqual(
            float(total_row['total_embodied_emissions_kgco2e']),
            3.0,
        )
        self.assertEqual(
            float(total_row['total_end_of_life_emissions_kgco2e']),
            6.0,
        )
        self.assertEqual(
            float(total_row['total_lca_emissions_kgco2e']),
            9.0,
        )

    def test_post_emissions_invalid_export_format(self):
        response = self.client.post(
            '/emissions?export=pdf',
            json=self.valid_payload
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            'Unsupported export format',
            response.get_data(as_text=True),
        )

    @patch(
        'src.jug_lca_buildings.application.jug_lca_buildings.LCACarbonWorkflow'
    )
    def test_post_emissions_uses_cached_result_on_repeat(
        self,
        workflow_cls_mock,
    ):
        workflow_cls_mock.return_value.export_emissions.return_value = (
            self.workflow_result
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {'JUG_LCA_ARTIFACTS_DIR': tmp_dir}):
                response_1 = self.client.post(
                    '/emissions',
                    json=self.valid_payload,
                )
                response_2 = self.client.post(
                    '/emissions',
                    json=self.valid_payload,
                )

        self.assertEqual(response_1.status_code, 201)
        self.assertEqual(response_2.status_code, 201)
        self.assertEqual(response_1.get_json(), self.workflow_result)
        self.assertEqual(response_2.get_json(), self.workflow_result)
        workflow_cls_mock.assert_called_once()

    @patch(
        'src.jug_lca_buildings.application.jug_lca_buildings.LCACarbonWorkflow'
    )
    def test_post_emissions_upload_multipart_contract(self, workflow_cls_mock):
        workflow_cls_mock.return_value.export_emissions.return_value = (
            self.workflow_result
        )
        file_obj = io.BytesIO(json.dumps(self.valid_payload).encode('utf-8'))

        response = self.client.post(
            '/emissions/upload',
            data={'geojson_file': (file_obj, 'city.geojson')},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), self.workflow_result)
        workflow_cls_mock.assert_called_once_with(
            self.valid_payload,
            'nrcan_archetypes.json',
            'nrcan_constructions_cap_3.json'
        )

    def test_post_emissions_upload_invalid_json_file(self):
        bad_json_file = io.BytesIO(b'{"type": "FeatureCollection", invalid}')

        response = self.client.post(
            '/emissions/upload',
            data={'geojson_file': (bad_json_file, 'bad.geojson')},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            'Invalid JSON content in geojson_file',
            response.get_data(as_text=True),
        )

    def test_post_emissions_upload_schema_validation_error(self):
        invalid_payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": 1,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-73.57, 45.5],
                                [-73.56, 45.5],
                                [-73.56, 45.51],
                                [-73.57, 45.5]
                            ]
                        ]
                    }
                    # "properties" intentionally missing for schema error
                }
            ]
        }
        file_obj = io.BytesIO(json.dumps(invalid_payload).encode('utf-8'))

        response = self.client.post(
            '/emissions/upload',
            data={'geojson_file': (file_obj, 'invalid.geojson')},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn('Invalid GeoJSON payload',
                      response.get_data(as_text=True))
