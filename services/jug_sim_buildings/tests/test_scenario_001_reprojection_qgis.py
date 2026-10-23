"""
Sabu project
jug_sim_buildings package
test_scenario_001_reprojection_qgis module
Verify actual CityGISOO transforms and final geometry preservation.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from jug_sim_buildings.scenario_001.config import ScenarioConfig
from jug_sim_buildings.scenario_001.reprojection import (
    CityGISOOReprojector, check_capability, geometry_structure, verify_final,
)
from test_scenario_001_preparation import feature, saved_run
from jug_sim_buildings.scenario_001.preparation import prepare_run


class TestQGISReprojection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            check_capability()
        except (ImportError, RuntimeError) as exc:
            raise unittest.SkipTest(f'Configured CityGISOO/QGIS runtime unavailable: {exc}')
        cls.backend = CityGISOOReprojector()

    @classmethod
    def tearDownClass(cls):
        cls.backend.close()

    def test_actual_transforms_preserve_parts_holes_attributes_and_source(self):
        from pyproj import Transformer
        for crs in ('EPSG:4617', 'EPSG:2950', 'EPSG:4326'):
            for geometry_type in ('Polygon', 'MultiPolygon'):
                with self.subTest(crs=crs, geometry_type=geometry_type), TemporaryDirectory() as directory:
                    polygon = [
                        [[-73.6, 45.5], [-73.59, 45.5], [-73.59, 45.51], [-73.6, 45.51], [-73.6, 45.5]],
                        [[-73.598, 45.502], [-73.598, 45.504], [-73.596, 45.504],
                         [-73.596, 45.502], [-73.598, 45.502]],
                    ]
                    second = [[[x + 0.02, y] for x, y in polygon[0]]]
                    reference = feature(100000)
                    reference['geometry'] = {'type': geometry_type,
                        'coordinates': polygon if geometry_type == 'Polygon' else [polygon, second]}
                    source = deepcopy(reference)
                    to_source = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
                    parts = [source['geometry']['coordinates']] if geometry_type == 'Polygon' else source['geometry']['coordinates']
                    for part in parts:
                        for ring in part:
                            for i, point in enumerate(ring):
                                ring[i] = list(to_source.transform(*point))
                    snapshot = deepcopy(source)
                    config = ScenarioConfig('http://c', 'http://v', directory, fsa='H3B')
                    report = self.backend.resolve_crs([('source', crs)], config)
                    output = Path(directory) / 'final.geojson'
                    self.backend.transform([source], report, output, Path(directory))
                    final = json.loads(output.read_text())
                    verify_final(final['features'], [source], equivalent=crs == 'EPSG:4326')
                    actual = final['features'][0]
                    self.assertEqual(actual['id'], source['id'])
                    self.assertEqual(actual['properties'], source['properties'])
                    self.assertEqual(geometry_structure(actual['geometry']), geometry_structure(reference['geometry']))
                    out_parts = [actual['geometry']['coordinates']] if geometry_type == 'Polygon' else actual['geometry']['coordinates']
                    ref_parts = [reference['geometry']['coordinates']] if geometry_type == 'Polygon' else reference['geometry']['coordinates']
                    for actual_part, reference_part in zip(out_parts, ref_parts):
                        for actual_ring, reference_ring in zip(actual_part, reference_part):
                            for point, expected in zip(actual_ring, reference_ring):
                                self.assertAlmostEqual(point[0], expected[0], places=6)
                                self.assertAlmostEqual(point[1], expected[1], places=6)
                    self.assertEqual(source, snapshot)
                    self.assertNotIn('crs', final)

    def test_missing_ambiguous_crs_and_invalid_operation_fail(self):
        with TemporaryDirectory() as directory:
            config = ScenarioConfig('http://c', 'http://v', directory)
            urn = self.backend.resolve_crs([('a', {
                'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::4617'}})], config)
            self.assertEqual(urn['source_crs'], 'EPSG:4617')
            with self.assertRaisesRegex(ValueError, 'missing'):
                self.backend.resolve_crs([], config)
            with self.assertRaisesRegex(ValueError, 'disagree'):
                self.backend.resolve_crs([('a', 'EPSG:4617'), ('b', 'EPSG:4326')], config)
            report = self.backend.resolve_crs([('a', 'EPSG:4617')], config)
            with self.assertRaises((ValueError, RuntimeError)):
                self.backend.transform([feature()], report, Path(directory) / 'final.geojson',
                                       directory, 'not-a-valid-coordinate-operation')
            self.assertFalse((Path(directory) / 'final.geojson').exists())

    def test_mixed_polygon_types_and_vertical_ordinates_preserve_identity(self):
        with TemporaryDirectory() as directory:
            polygon = feature(3)
            multipart = feature(4)
            ring = [[*point, 17.5] for point in multipart['geometry']['coordinates'][0]]
            multipart['geometry'] = {'type': 'MultiPolygon', 'coordinates': [[ring]]}
            inputs = [polygon, multipart]
            config = ScenarioConfig('http://c', 'http://v', directory)
            report = self.backend.resolve_crs([('a', 'EPSG:4617')], config)
            output = Path(directory) / 'final.geojson'
            self.backend.transform(inputs, report, output, directory)
            final = json.loads(output.read_text())['features']
            verify_final(final, inputs)
            self.assertEqual([f['id'] for f in final], [3, 4])
            self.assertEqual([f['geometry']['type'] for f in final], ['Polygon', 'MultiPolygon'])

    def test_saved_run_uses_original_crs_without_retained_crs_and_preserves_sources(self):
        with TemporaryDirectory() as directory:
            store = saved_run(directory)
            config = ScenarioConfig('http://c', 'http://v', directory, fsa='H3B')
            hashes = {p: p.read_bytes() for p in store.directory.rglob('*') if p.is_file()}
            result = prepare_run(store.directory, config, reprojector=self.backend)
            report = json.loads((Path(result['preparation_directory']) / 'crs.json').read_text())
            self.assertEqual(report['source_crs'], 'EPSG:4326')
            self.assertEqual(report['status'], 'copied')
            for path, data in hashes.items():
                self.assertEqual(path.read_bytes(), data)
