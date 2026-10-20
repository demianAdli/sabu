"""Synchronous uniquification with no census, comparison, or plot workflow."""
from __future__ import annotations

import logging

from flask import request
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from marshmallow import ValidationError

from ..application.uniquification import GISUniquificationApplicationService
from ..errors import GISValidationDataContractError, GISValidationInputError
from ..schemas import (
    GISUniquificationRequestSchema,
    GISUniquificationResultSchema,
)


logger = logging.getLogger(__name__)
blp = Blueprint('GIS Uniquifications', __name__,
                description='Standalone feature uniquification.')


@blp.route('/uniquifications')
class GISUniquifications(MethodView):
    """Retain the greatest-area feature per non-missing identifier."""

    @blp.response(200, GISUniquificationResultSchema)
    @blp.doc(requestBody={
        'required': True,
        'content': {'application/json': {'schema': GISUniquificationRequestSchema}},
    })
    @blp.alt_response(400, description='Invalid JSON, GeoJSON, or input path.')
    @blp.alt_response(422, description='Invalid request or uniquification data contract.')
    @blp.alt_response(500, description='Unexpected uniquification failure.')
    def post(self):
        """Uniquify features and return retained GeoJSON, counts, and trace."""
        if request.args:
            abort(400, message='Standalone uniquification does not accept query options.')
        payload = request.get_json(silent=True)
        if payload is None:
            abort(400, message='Request body must be valid JSON.')
        try:
            data = GISUniquificationRequestSchema().load(payload)
        except ValidationError as exc:
            abort(422, message='Invalid uniquification request payload',
                  errors=exc.messages)
        try:
            result = GISUniquificationApplicationService.run_uniquification(
                data.get('buildings_set', data.get('buildings_set_path')),
                unique_attribute_key=data['unique_attribute_key'],
                area_key=data['area_key'])
            return result.as_dict()
        except GISValidationInputError as exc:
            abort(400, message=str(exc))
        except GISValidationDataContractError as exc:
            abort(422, message=str(exc))
        except Exception:
            logger.exception('gis_uniquification_failed')
            abort(500, message='Failed to run GIS uniquification')
