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
from marshmallow import Schema, fields


class GeometrySchema(Schema):
    """Schema for the geometry of a feature."""
    type = fields.String(required=True)
    coordinates = fields.List(
        fields.List(fields.List(fields.Float())), required=True)


class PropertiesSchema(Schema):
    """Schema for the properties of a feature."""
    name = fields.String(required=True)
    address = fields.String(required=True)
    function = fields.String(required=True)
    height = fields.Float(required=True)
    year_of_construction = fields.Integer(required=True)


class FeatureSchema(Schema):
    """Schema for a GeoJSON feature."""
    type = fields.String(required=True)
    geometry = fields.Nested(GeometrySchema, required=True)
    id = fields.Integer(required=True)
    properties = fields.Nested(PropertiesSchema, required=True)


class LCAInputDataSchema(Schema):
    """Define variables that come from user input."""
    type = fields.String(required=True)
    features = fields.List(fields.Nested(FeatureSchema), required=True)


class GeoJSONUploadSchema(Schema):
    """Schema for multipart GeoJSON upload payload."""
    geojson_file = fields.Field(
        required=True,
        metadata={"type": "string", "format": "binary"}
    )
