"""
Sabu project
jug_lca_buildings package
emissions module
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import json
import logging
import os

from flask import current_app, jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException

from ..application import EmissionsApplicationService
from ..schemas.schemas import (
    GeoJSONUploadSchema,
    LCAInputDataSchema,
)
from ..reporting import EmissionsReportExporter

logger = logging.getLogger(__name__)
DEV_MODE = os.getenv('LOG_ENV', 'dev') == 'dev'

blp = Blueprint(
    'Emissions',
    __name__,
    description=(
        'Exporting embodied and end-of-life emissions data for buildings'
    ),
)


def _run_emissions_workflow(
    request_city,
    request_received_log,
    request_failed_log,
):
    export_format = (request.args.get('export') or '').strip().lower()
    if export_format and export_format != 'csv':
        abort(400, message="Unsupported export format. Supported values: csv")

    logger.info(request_received_log)
    try:
        computation_result = (
            EmissionsApplicationService.compute_emissions(
                request_city
            )
        )
        emissions_data = computation_result.emissions_data
        logger.info(
            "emissions_request_succeeded",
            extra={
                'buildings': len(emissions_data),
                'cache_hit': computation_result.cache_hit,
                'request_hash': computation_result.request_hash[:12],
            },
        )
        if export_format == 'csv':
            csv_export = EmissionsApplicationService.build_csv_report(
                request_city,
                computation_result,
            )
            logger.info(
                "emissions_report_export_succeeded",
                extra={
                    'format': 'csv',
                    'buildings': len(emissions_data),
                    'csv_cache_hit': csv_export['cache_hit'],
                    'request_hash': computation_result.request_hash[:12],
                },
            )
            return (
                EmissionsReportExporter.to_csv_download_response_with_filename(
                    csv_export['csv_text'],
                    csv_export['filename'],
                ),
                200,
            )
        return jsonify(emissions_data), 201

    except HTTPException:
        # If something upstream already called abort(...), preserve response.
        raise

    except Exception as e:
        logger.exception(request_failed_log)
        public_msg = (
            str(e) if (DEV_MODE or current_app.debug)
            else 'Failed to compute emissions'
        )
        abort(500, message=public_msg)


@blp.route('/emissions')
class Emissions(MethodView):
    @blp.arguments(LCAInputDataSchema)
    def post(self, request_city):
        return _run_emissions_workflow(
            request_city,
            request_received_log='emissions_request_received',
            request_failed_log='emissions_request_failed',
        )


@blp.route('/emissions/upload')
class EmissionsUpload(MethodView):
    @blp.arguments(GeoJSONUploadSchema, location='files')
    def post(self, files_data):
        geojson_file = files_data['geojson_file']

        if not geojson_file or not getattr(geojson_file, "filename", ""):
            abort(400, message="geojson_file is required")

        try:
            request_city = json.load(geojson_file.stream)
        except json.JSONDecodeError:
            abort(400, message="Invalid JSON content in geojson_file")
        else:
            try:
                validated_request_city = LCAInputDataSchema().load(
                    request_city
                )
            except ValidationError as err:
                abort(
                    422,
                    message="Invalid GeoJSON payload",
                    errors=err.messages,
                )
            else:
                return _run_emissions_workflow(
                    validated_request_city,
                    request_received_log='emissions_upload_request_received',
                    request_failed_log='emissions_upload_request_failed',
                )
