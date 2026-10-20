"""Read real geometry with the pinned hub dependency, without running LCA."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from pyproj import Transformer

from src.jug_lca_buildings.lca_carbon_workflow import GeometryFactory
from tests.geometry_fixtures import geometry_cities


def projected_ring_area(ring, transformer):
    points = [transformer.transform(x, y) for x, y in ring]
    origin_x, origin_y = points[0]
    points = [(x - origin_x, y - origin_y) for x, y in points]
    return abs(sum(x1 * y2 - x2 * y1
                   for (x1, y1), (x2, y2) in zip(points, points[1:]))) / 2


class TestGeojsonGeometry(unittest.TestCase):
    def test_real_reader_preserves_parts_holes_and_one_building_per_feature(self):
        for label, payload in geometry_cities():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                original = deepcopy(payload)
                source = Path(tmp) / 'buildings.geojson'
                source.write_text(json.dumps(payload), encoding='utf-8')
                original_bytes = source.read_bytes()
                city = GeometryFactory(
                    'geojson', path=source, height_field='height',
                    year_of_construction_field='year_of_construction',
                    function_field='function', aliases_field=['name'],
                ).city
                self.assertEqual(len(city.buildings), len(payload['features']))
                transformer = Transformer.from_crs('EPSG:4326', city.srs_name, always_xy=True)
                for feature, building in zip(payload['features'], city.buildings):
                    geometry = feature['geometry']
                    polygons = (geometry['coordinates'] if geometry['type'] == 'MultiPolygon'
                                else [geometry['coordinates']])
                    self.assertEqual(building.name, str(feature['id']))
                    self.assertEqual(building.aliases, [feature['properties']['name']])
                    self.assertEqual(building.function, feature['properties']['function'])
                    self.assertEqual(building.year_of_construction, 1995)
                    self.assertEqual(len(building.grounds), len(polygons))
                    self.assertEqual(len(building.roofs), len(polygons))
                    areas = []
                    for polygon, ground in zip(polygons, building.grounds):
                        exterior_area = projected_ring_area(polygon[0], transformer)
                        hole_area = sum(projected_ring_area(hole, transformer) for hole in polygon[1:])
                        expected_area = exterior_area - hole_area
                        self.assertLess(expected_area, exterior_area)
                        self.assertAlmostEqual(ground.solid_polygon.area, expected_area, delta=.01)
                        areas.append(expected_area)
                    self.assertAlmostEqual(building.floor_area, sum(areas), delta=.02)
                    self.assertAlmostEqual(building.volume,
                                           sum(areas) * feature['properties']['height'], delta=.3)
                self.assertEqual(payload, original)
                self.assertEqual(source.read_bytes(), original_bytes)

    def test_single_polygon_and_single_part_multipolygon_have_equal_surfaces(self):
        cities = []
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'buildings.geojson'
            for _, payload in geometry_cities()[:2]:
                source.write_text(json.dumps(payload), encoding='utf-8')
                cities.append(GeometryFactory('geojson', path=source, height_field='height').city)
        polygon, multipolygon = [city.buildings[0] for city in cities]
        self.assertEqual(len(polygon.surfaces), len(multipolygon.surfaces))
        self.assertEqual(polygon.floor_area, multipolygon.floor_area)
        self.assertEqual(polygon.volume, multipolygon.volume)
        for first, second in zip(polygon.surfaces, multipolygon.surfaces):
            self.assertEqual([list(point) for point in first.solid_polygon.coordinates],
                             [list(point) for point in second.solid_polygon.coordinates])

    def test_multipart_without_holes_and_without_extrusion(self):
        payload = geometry_cities()[2][1]
        polygons = payload['features'][0]['geometry']['coordinates']
        polygons[:] = [[polygon[0]] for polygon in polygons]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'buildings.geojson'
            source.write_text(json.dumps(payload), encoding='utf-8')
            for height_field in ('height', None):
                with self.subTest(height_field=height_field):
                    city = GeometryFactory('geojson', path=source,
                                           height_field=height_field).city
                    self.assertEqual(len(city.buildings), 1)
                    building = city.buildings[0]
                    self.assertEqual(len(building.grounds), 2)
                    self.assertEqual(len(building.roofs), 2 if height_field else 0)
                    transformer = Transformer.from_crs(
                        'EPSG:4326', city.srs_name, always_xy=True)
                    expected = sum(projected_ring_area(part[0], transformer)
                                   for part in polygons)
                    self.assertAlmostEqual(building.floor_area, expected, delta=.02)
