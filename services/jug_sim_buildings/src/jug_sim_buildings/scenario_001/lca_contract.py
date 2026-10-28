"""
Sabu project
jug_sim_buildings package
lca_contract module
Normalize LCA fields and report scenario eligibility errors.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import math

from marshmallow import ValidationError, fields


SCENARIO_RULES = [
    'Prepared IDs are unique nonnegative integers no greater than 2**53-1.',
    'Required strings must be nonblank; height and construction year must be positive.',
    'Construction years must be exact integers, never truncated.',
    'citygisoo_area must be present, numeric, finite, and at least 25 m2.',
    'Geometry must be a nonempty valid Polygon/MultiPolygon with closed rings.',
]


def normalize_feature(feature):
    """Normalize on a copy; retain extra properties and collect every offending field."""
    output = deepcopy(feature)
    errors, changes = [], []
    properties = output['properties']

    def error(field, reason, value):
        errors.append({'field': field, 'reason': reason, 'value': deepcopy(value)})

    for key in ('name', 'address', 'function', 'height', 'year_of_construction'):
        value = properties.get(key)
        try:
            if key in ('name', 'address', 'function'):
                normalized = fields.String(required=True).deserialize(value).strip()
                if not normalized:
                    raise ValueError('Required string is blank (scenario rule).')
            elif key == 'height':
                if isinstance(value, bool):
                    raise ValueError('Boolean is not a height.')
                normalized = fields.Float(required=True).deserialize(value)
                if not math.isfinite(normalized) or normalized <= 0:
                    raise ValueError('Height must be finite and positive (scenario rule).')
            else:
                if isinstance(value, bool):
                    raise ValueError('Boolean is not a construction year.')
                normalized = fields.Integer(required=True).deserialize(value)
                exact = Decimal(str(value))
                if not exact.is_finite() or exact != normalized or normalized <= 0:
                    raise ValueError('Year must be a positive exact integer (scenario rule).')
            properties[key] = normalized
            if type(value) is not type(normalized) or value != normalized:
                changes.append({'field': key, 'original': value, 'normalized': normalized})
        except (ValidationError, ValueError, TypeError, OverflowError, InvalidOperation) as exc:
            error(f'properties.{key}', str(exc), value)

    area_value = properties.get('citygisoo_area')
    try:
        if 'citygisoo_area' not in properties:
            raise ValueError('citygisoo_area is missing.')
        if area_value is None:
            raise ValueError('citygisoo_area is null.')
        if isinstance(area_value, bool):
            raise ValueError('Boolean is not a citygisoo_area.')
        area = fields.Float(required=True).deserialize(area_value)
        if not math.isfinite(area):
            raise ValueError('citygisoo_area must be finite.')
        if area < 25:
            raise ValueError('citygisoo_area is below the minimum of 25 m2 (scenario rule).')
    except (ValidationError, ValueError, TypeError, OverflowError) as exc:
        error('properties.citygisoo_area', str(exc), area_value)

    geometry = output.get('geometry')
    try:
        if not isinstance(geometry, dict) or geometry.get('type') not in ('Polygon', 'MultiPolygon'):
            raise ValueError('Only Polygon/MultiPolygon geometry is supported.')
        coordinates = geometry.get('coordinates')
        polygons = [coordinates] if geometry['type'] == 'Polygon' else coordinates
        if not isinstance(polygons, list) or not polygons:
            raise ValueError('Empty or missing polygon parts.')
        for polygon in polygons:
            if not isinstance(polygon, list) or not polygon:
                raise ValueError('Empty or missing polygon rings.')
            for ring in polygon:
                if not isinstance(ring, list) or len(ring) < 4:
                    raise ValueError('A ring needs at least four positions including closure.')
                for position, point in enumerate(ring):
                    if not isinstance(point, list) or len(point) not in (2, 3, 4):
                        raise ValueError('Positions must have two to four ordinates.')
                    if any(isinstance(v, bool) for v in point):
                        raise ValueError('Boolean coordinate.')
                    numeric = [fields.Float().deserialize(v) for v in point]
                    if not all(math.isfinite(v) for v in numeric):
                        raise ValueError('Non-finite coordinate.')
                    ring[position] = numeric
                if ring[0] != ring[-1]:
                    raise ValueError('Ring is not closed; no geometry repair is performed.')
    except (ValueError, TypeError, ValidationError, OverflowError) as exc:
        error('geometry', str(exc), geometry)
    return output, errors, changes
