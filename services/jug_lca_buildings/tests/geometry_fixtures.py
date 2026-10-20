"""WGS84 footprints with exterior rings, holes, and separated building parts."""

from copy import deepcopy

from tests.test_input_validation import valid_city


def polygon_with_hole(x=-73.57, y=45.5):
    exterior = [[x, y], [x + .001, y], [x + .001, y + .001],
                [x, y + .001], [x, y]]
    hole = [[x + .0002, y + .0002], [x + .0002, y + .0004],
            [x + .0004, y + .0004], [x + .0004, y + .0002],
            [x + .0002, y + .0002]]
    return [exterior, hole]


def geometry_cities():
    polygon = valid_city()
    polygon['features'][0]['geometry']['coordinates'] = polygon_with_hole()
    single = deepcopy(polygon)
    single['features'][0]['geometry'] = {
        'type': 'MultiPolygon', 'coordinates': [polygon_with_hole()]}
    multipart = deepcopy(single)
    multipart['features'][0]['geometry']['coordinates'].append(
        polygon_with_hole(-73.568))
    mixed = deepcopy(polygon)
    second = deepcopy(multipart['features'][0])
    second['id'] = 2
    second['geometry']['coordinates'] = [
        polygon_with_hole(-73.565), polygon_with_hole(-73.563)]
    mixed['features'].append(second)
    return [('polygon_hole', polygon), ('single_multipolygon', single),
            ('multipart_holes', multipart), ('mixed', mixed)]


def invalid_geometries():
    polygon = polygon_with_hole()
    for geometry_type, coordinates in (
        ('Polygon', [polygon]),             # MultiPolygon depth
        ('MultiPolygon', polygon),          # Polygon depth
        ('MultiPolygon', None),
        ('MultiPolygon', [None]),
        ('MultiPolygon', [[None]]),
        ('MultiPolygon', [[[None]]]),
        ('MultiPolygon', [[[['bad', 45.5]]]]),
        ('MultiPolygon', [[[[None, 45.5]]]]),
        ('MultiPolygon', [[[[float('inf'), 45.5]]]]),
        ('MultiPolygon', [[[[float('nan'), 45.5]]]]),
        ('Point', [-73.57, 45.5]),
        ('LineString', [[-73.57, 45.5], [-73.56, 45.5]]),
        ('GeometryCollection', []),
        ('unknown', []),
        (None, []),
        ([], []),
    ):
        yield {'type': geometry_type, 'coordinates': coordinates}
    yield {'type': 'MultiPolygon'}
    yield {'coordinates': [polygon]}


def add_metadata_and_numeric_strings(city):
    decorated = deepcopy(city)
    decorated['source'] = {'provider': 'survey'}
    for feature in decorated['features']:
        feature['bbox'] = []
        feature['geometry']['source'] = 'GIS'
        feature['properties']['extra'] = None
        feature['id'] = str(feature['id'])
        feature['properties']['height'] = str(feature['properties']['height'])
        feature['properties']['year_of_construction'] = '1995'
        position = feature['geometry']['coordinates']
        while isinstance(position[0], list):
            position = position[0]
        position[0] = str(position[0])
    return decorated
