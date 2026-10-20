"""Read real geometry with the pinned hub dependency, without running LCA."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from pyproj import Transformer
from unittest.mock import patch
from hub.imports.geometry.geojson import Geojson

from src.jug_lca_buildings.lca_carbon_workflow import GeometryFactory
from src.jug_lca_buildings.life_cycle_assessment.geojson_geometry import BuildingGeojson
from src.jug_lca_buildings.schemas.schemas import LCAInputDataSchema
from tests.geometry_fixtures import clockwise_city, geometry_cities, with_reversed_rings


def projected_ring_area(ring, transformer):
    points = [transformer.transform(x, y) for x, y in ring]
    origin_x, origin_y = points[0]
    points = [(x - origin_x, y - origin_y) for x, y in points]
    return abs(sum(x1 * y2 - x2 * y1
                   for (x1, y1), (x2, y2) in zip(points, points[1:]))) / 2


class TestGeojsonGeometry(unittest.TestCase):
    def _read_city(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'buildings.geojson'
            source.write_text(json.dumps(payload), encoding='utf-8')
            before = source.read_bytes()
            city = GeometryFactory(
                'geojson', path=source, height_field='height',
                year_of_construction_field='year_of_construction',
                function_field='function',
            ).city
            self.assertEqual(source.read_bytes(), before)
            return city

    def test_both_windings_preserve_polygon_parts_holes_areas_and_volumes(self):
        for label, payload in geometry_cities():
            expected = self._read_city(payload)
            for exterior in (False, True):
                for holes in (False, True):
                    with self.subTest(label=label, exterior=exterior, holes=holes):
                        variant = with_reversed_rings(payload, exterior, holes)
                        original = deepcopy(variant)
                        city = self._read_city(variant)
                        self.assertEqual(len(city.buildings), len(expected.buildings))
                        for building, reference in zip(city.buildings, expected.buildings):
                            self.assertEqual(building.name, reference.name)
                            self.assertEqual(len(building.grounds), len(reference.grounds))
                            self.assertEqual(len(building.roofs), len(reference.roofs))
                            self.assertEqual(building.floor_area, reference.floor_area)
                            self.assertEqual(building.volume, reference.volume)
                            self.assertEqual(len(building.surfaces), len(reference.surfaces))
                            for surface, original_surface in zip(building.surfaces, reference.surfaces):
                                self.assertEqual(
                                    [list(point) for point in surface.solid_polygon.coordinates],
                                    [list(point) for point in original_surface.solid_polygon.coordinates])
                        self.assertEqual(variant, original)

    def test_reported_clockwise_footprint_as_polygon_and_multipolygon(self):
        payload = LCAInputDataSchema().load(clockwise_city())
        for geometry_type in ('Polygon', 'MultiPolygon'):
            with self.subTest(geometry_type=geometry_type):
                variant = deepcopy(payload)
                if geometry_type == 'Polygon':
                    geometry = variant['features'][0]['geometry']
                    geometry['type'] = 'Polygon'
                    geometry['coordinates'] = geometry['coordinates'][0]
                original = deepcopy(variant)
                city = self._read_city(variant)
                self.assertEqual(len(city.buildings), 1)
                building = city.buildings[0]
                self.assertEqual(building.name, '100000')
                self.assertEqual(len(building.grounds), 1)
                ring = payload['features'][0]['geometry']['coordinates'][0][0]
                transformer = Transformer.from_crs('EPSG:4326', city.srs_name, always_xy=True)
                area = projected_ring_area(ring, transformer)
                self.assertAlmostEqual(building.floor_area, area, delta=.001)
                self.assertAlmostEqual(building.volume, area * 9.82870101928711, delta=.01)
                self.assertEqual(variant, original)

    def test_reader_only_reorders_copied_positions_preserving_extra_ordinates(self):
        canonical = geometry_cities()[0][1]['features'][0]['geometry']['coordinates']
        for ring in canonical:
            for position in ring:
                position.append(12.5)
        reversed_rings = [list(reversed(ring)) for ring in canonical]
        original = deepcopy(reversed_rings)
        reader = object.__new__(BuildingGeojson)
        with patch.object(Geojson, '_parse_polygon', autospec=True) as parse:
            reader._parse_polygon(reversed_rings, '1', [], '1000', 1995, 10)
            passed_coordinates = parse.call_args.args[1]
            self.assertEqual(passed_coordinates, canonical)
            self.assertEqual(reversed_rings, original)
            self.assertIsNot(passed_coordinates[0][0], reversed_rings[0][0])

    def test_winding_normalization_does_not_repair_incomplete_rings(self):
        reader = object.__new__(BuildingGeojson)
        for coordinates in ([], [[]], [[[1]]], [[[1, 2], [2, 3]]]):
            with self.subTest(coordinates=coordinates), patch.object(
                Geojson, '_parse_polygon', autospec=True
            ) as parse:
                reader._parse_polygon(coordinates, '1', [], '1000', 1995, 10)
                self.assertEqual(parse.call_args.args[1], coordinates)

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
