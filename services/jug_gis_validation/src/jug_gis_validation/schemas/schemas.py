"""
Sabu project
jug_gis_validation project
jug_gis_validation package
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
https://demianadli.com/

Marshmallow schemas for GISOO validation API requests and responses.

"""
from __future__ import annotations

from marshmallow import (
    EXCLUDE,
    Schema,
    fields,
    validate,
    validates_schema,
    ValidationError,
)

from ..application.jug_gis_validation import (
    AreaCalculationMode,
    DEFAULT_AREA_KEY,
    DEFAULT_CENSUS_CODE_FIELD_TITLE,
    DEFAULT_CENSUS_UNITS_NUM_TITLE,
    DEFAULT_FLOOR_NUM_KEY,
    DEFAULT_FUNCTION_KEY,
    DEFAULT_FUNCTION_VALUE,
    DEFAULT_HEIGHT_KEY,
    DEFAULT_POSTAL_CODE_KEY,
)


class GISValidationRequestSchema(Schema):
    """Request body for validating a buildings_set."""

    class Meta:
        unknown = EXCLUDE

    buildings_set = fields.Raw(load_default=None)
    buildings_set_path = fields.String(load_default=None)

    census_code_field_title = fields.String(
        load_default=DEFAULT_CENSUS_CODE_FIELD_TITLE)
    census_units_num_title = fields.String(
        load_default=DEFAULT_CENSUS_UNITS_NUM_TITLE)
    postal_code_key = fields.String(load_default=DEFAULT_POSTAL_CODE_KEY)
    function_key = fields.String(load_default=DEFAULT_FUNCTION_KEY)
    function_value = fields.Raw(load_default=DEFAULT_FUNCTION_VALUE)
    cleaned_units_num_key = fields.String(load_default=None, allow_none=True)
    area_key = fields.String(load_default=DEFAULT_AREA_KEY)
    floor_num_key = fields.String(load_default=DEFAULT_FLOOR_NUM_KEY)
    area_calculation_mode = fields.String(
        load_default=AreaCalculationMode.AREA_TIMES_FLOOR.value,
        validate=validate.OneOf([mode.value for mode in AreaCalculationMode]))
    height_key = fields.String(load_default=DEFAULT_HEIGHT_KEY)
    include_height_proxy = fields.Boolean(load_default=False)
    height_proxy_area_key = fields.String(load_default=None, allow_none=True)
    height_proxy_area_fallback_key = fields.String(
        load_default=None,
        allow_none=True)
    height_proxy_area_fallback_value = fields.Float(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=0, min_inclusive=False))
    unique_attribute_key = fields.String(load_default=None, allow_none=True)
    uniquification_area_key = fields.String(load_default=None, allow_none=True)
    census_avg_area_by_type = fields.Dict(
        keys=fields.String(),
        values=fields.Float(),
        load_default=None)
    district_name = fields.String(load_default='validation')
    plot_title = fields.String(load_default=None)

    @validates_schema
    def validate_buildings_input(self, data, **kwargs):
        has_content = data.get('buildings_set') is not None
        has_path = bool(data.get('buildings_set_path'))
        if not has_content and not has_path:
            raise ValidationError(
                'Either buildings_set or buildings_set_path is required.')
        if has_content and has_path:
            raise ValidationError(
                'Provide only one of buildings_set or buildings_set_path.')
        if (
                data.get('height_proxy_area_fallback_key') is not None
                and data.get('height_proxy_area_fallback_value') is not None):
            raise ValidationError(
                'Provide only one of height_proxy_area_fallback_key or '
                'height_proxy_area_fallback_value.')
        if (
                data.get('area_calculation_mode')
                == AreaCalculationMode.NONE.value
                and data.get('include_height_proxy')):
            raise ValidationError(
                'include_height_proxy cannot be enabled when '
                'area_calculation_mode is none.')


class GeoJSONUploadSchema(Schema):
    """Multipart upload schema for a buildings_set GeoJSON file."""

    geojson_file = fields.Field(
        required=True,
        metadata={"type": "string", "format": "binary"})


class GISValidationResultSchema(Schema):
    """JSON response for a validation run."""

    codes = fields.List(fields.String(), required=True)
    rows_count = fields.Integer(required=True)
    comparison_table = fields.List(fields.Dict(), required=True)
    uniquification = fields.Dict(required=True)
    area_calculation_mode = fields.String(required=True)
    height_proxy_included = fields.Boolean(required=True)
    height_proxy_area_key = fields.String(required=True, allow_none=True)
    height_proxy_area_resolution = fields.Dict(required=True, allow_none=True)


class GISUniquificationRequestSchema(Schema):
    """Standalone operation: unknown fields, including validation options, fail."""

    buildings_set = fields.Raw()
    buildings_set_path = fields.String(validate=validate.Regexp(r'(?s).*\S'))
    unique_attribute_key = fields.String(
        required=True, validate=validate.Regexp(r'(?s).*\S'))
    area_key = fields.String(
        load_default='area', validate=validate.Regexp(r'(?s).*\S'))

    @validates_schema
    def validate_buildings_input(self, data, **kwargs):
        if ('buildings_set' in data) == ('buildings_set_path' in data):
            raise ValidationError(
                'Provide exactly one of buildings_set or buildings_set_path.')
        if 'buildings_set' in data:
            content = data['buildings_set']
            if not isinstance(content, dict) or content.get('type') != 'FeatureCollection':
                raise ValidationError(
                    'buildings_set must be a GeoJSON FeatureCollection.',
                    field_name='buildings_set')


class GISUniquificationResultSchema(Schema):
    """Complete result, including positional mappings for removed records."""

    uniquification = fields.Dict(required=True)
    retained_geojson = fields.Dict(required=True)
    records = fields.List(fields.Dict(), required=True)
