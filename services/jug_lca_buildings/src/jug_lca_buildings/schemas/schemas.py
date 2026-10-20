"""
Sabu project
jug_lca_buildings package
schemas module
Defines the schemas to post on emissions.py
Project Designer and Developer: Alireza Adli
Licensed under the Apache License, Version 2.0.
Project developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate


GEOMETRY_COORDINATE_DEPTHS = {'Polygon': 3, 'MultiPolygon': 4}


def _coordinate_field(depth):
    field = fields.Float()
    for _ in range(depth):
        field = fields.List(field)
    return field


def _geometry_contract(geometry_type, depth):
    coordinates = {'type': 'number'}
    for _ in range(depth):
        coordinates = {'type': 'array', 'items': coordinates}
    return {
        'type': 'object',
        'required': ['type', 'coordinates'],
        'additionalProperties': True,
        'properties': {
            'type': {'type': 'string', 'enum': [geometry_type]},
            'coordinates': coordinates,
        },
    }


class GeometryCoordinates(fields.Field):
    """Load numeric coordinates using the declared geometry's nesting depth."""

    def _deserialize(self, value, attr, data, **kwargs):
        try:
            geometry_type = self.parent.fields['type'].deserialize(data.get('type'))
        except ValidationError as err:
            # The type field also reports its own missing/invalid value.
            raise ValidationError(
                'Coordinates require type Polygon or MultiPolygon.'
            ) from err
        return _coordinate_field(
            GEOMETRY_COORDINATE_DEPTHS[geometry_type]
        ).deserialize(value)


class GeometrySchema(Schema):
    """Schema for the geometry of a feature."""
    class Meta:
        unknown = EXCLUDE

    type = fields.String(
        required=True, validate=validate.OneOf(GEOMETRY_COORDINATE_DEPTHS))
    coordinates = GeometryCoordinates(required=True)


class GeometryField(fields.Field):
    """Nested geometry validation with type-specific generated API schemas."""

    def __init__(self, **kwargs):
        super().__init__(metadata={
            'description': (
                'Polygon or MultiPolygon; coordinate nesting follows type. '
                'Unknown metadata is accepted and excluded. Either ring winding '
                'is accepted; the reader orients a working copy without changing '
                'source coordinates, polygon parts, or holes.'),
            'oneOf': [
                _geometry_contract(geometry_type, depth)
                for geometry_type, depth in GEOMETRY_COORDINATE_DEPTHS.items()
            ],
        }, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        return GeometrySchema().load(value)


class PropertiesSchema(Schema):
    """Schema for the properties of a feature."""
    class Meta:
        unknown = EXCLUDE

    name = fields.String(required=True)
    address = fields.String(required=True)
    function = fields.String(required=True)
    height = fields.Float(required=True)
    year_of_construction = fields.Integer(required=True)


class FeatureSchema(Schema):
    """Schema for a GeoJSON feature."""
    class Meta:
        unknown = EXCLUDE

    type = fields.String(required=True)
    geometry = GeometryField(required=True)
    id = fields.Integer(required=True)
    properties = fields.Nested(PropertiesSchema, required=True)


class LCAInputDataSchema(Schema):
    """Define variables that come from user input."""
    class Meta:
        unknown = EXCLUDE

    type = fields.String(required=True)
    features = fields.List(fields.Nested(FeatureSchema), required=True)


class GeoJSONUploadSchema(Schema):
    """Schema for multipart GeoJSON upload payload."""
    geojson_file = fields.Field(
        required=True,
        metadata={"type": "string", "format": "binary"}
    )
