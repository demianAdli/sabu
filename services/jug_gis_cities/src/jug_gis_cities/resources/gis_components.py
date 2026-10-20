"""
Sabu project
jug_gis_cities package
gis_components resource module
REST resource for running city GIS cleaning components.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import logging
import os
import uuid
from contextlib import contextmanager

from flask import current_app, send_file, url_for
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from werkzeug.exceptions import HTTPException

from ..application import (
    FsaBatchRunner,
    GisComponentContractError,
    GisComponentError,
    GisComponentNotFoundError,
    GISCitiesApplicationService,
    normalize_fsas,
)
from ..application.batch_jobs import get_batch_job_store
from ..application.artifacts import (
    ArtifactError,
    ArtifactNotFoundError,
    ArtifactUnavailableError,
    get_artifact_store,
)
from ..schemas import (
    FsaBatchJobSchema,
    FsaBatchRunRequestSchema,
    GISComponentRunRequestSchema,
    GISComponentRunResultSchema,
)


logger = logging.getLogger(__name__)
DEV_MODE = os.getenv('LOG_ENV', 'dev') == 'dev'

blp = Blueprint(
    'GIS Components',
    __name__,
    description='Running city GIS cleaning components.',
)


def _artifact_response_fields(artifact_id):
    return {
        'standardized_artifact_id': artifact_id,
        'standardized_download_url': (
            url_for('.GISArtifactDownload', artifact_id=artifact_id,
                    _external=True) if artifact_id else None),
    }


def _batch_to_response(job):
    response = job.to_response()
    response['results'] = [
        {**item, **_artifact_response_fields(item.get('standardized_artifact_id'))}
        for item in response['results']
    ]
    return response


def _result_to_response(result):
    return {
        'component_name': result.component_name,
        'mode': result.mode.value,
        'fsa': result.fsa,
        'workflow_output_path': result.workflow_output_path,
        'standardized_output_path': result.standardized_output_path,
        'cleaned_output_paths': list(result.cleaned_output_paths),
        **_artifact_response_fields(result.standardized_artifact_id),
    }


@contextmanager
def _fsa_output_lock(component_name, fsa):
    if fsa is None:
        yield
        return
    normalized_fsa = normalize_fsas([fsa])[0]
    store = get_batch_job_store()
    owner_id = f'single-{uuid.uuid4().hex}'
    if not store.acquire_fsa_locks(
            owner_id,
            component_name,
            (normalized_fsa,)):
        abort(
            409,
            message=(
                f'GIS city component output is already being processed: '
                f'{component_name} {normalized_fsa}'))
    try:
        yield
    finally:
        store.release_fsa_locks(owner_id)


def _run_gis_component(component_name, request_data):
    mode = request_data.get('mode')
    fsa = request_data.get('fsa')
    drop_null_fields = request_data.get('drop_null_fields')
    cleanup_outputs = request_data.get('cleanup_outputs', False)
    keep_outputs = request_data.get('keep_outputs')
    logger.info(
        'gis_component_run_received',
        extra={
            'component_name': component_name,
            'mode': mode,
            'fsa': fsa,
            'drop_null_fields': drop_null_fields,
            'cleanup_outputs': cleanup_outputs,
            'keep_outputs': keep_outputs,
        },
    )

    try:
        with _fsa_output_lock(component_name, fsa):
            result = GISCitiesApplicationService.run_component(
                component_name=component_name,
                mode=mode,
                fsa=fsa,
                non_null_required_fields=drop_null_fields,
                cleanup_outputs=cleanup_outputs,
                keep_outputs=keep_outputs,
            )
    except HTTPException:
        raise
    except GisComponentNotFoundError as exc:
        logger.warning(
            'gis_component_run_not_found',
            extra={
                'component_name': component_name,
                'mode': mode,
                'fsa': fsa,
                'error': str(exc),
            },
        )
        abort(404, message=str(exc))
    except GisComponentContractError as exc:
        logger.warning(
            'gis_component_run_contract_invalid',
            extra={
                'component_name': component_name,
                'mode': mode,
                'fsa': fsa,
                'error': str(exc),
            },
        )
        abort(422, message=str(exc))
    except (TypeError, ValueError) as exc:
        logger.warning(
            'gis_component_run_bad_request',
            extra={
                'component_name': component_name,
                'mode': mode,
                'fsa': fsa,
                'error': str(exc),
            },
        )
        abort(400, message=str(exc))
    except GisComponentError as exc:
        logger.exception(
            'gis_component_run_failed',
            extra={
                'component_name': component_name,
                'mode': mode,
                'fsa': fsa,
            },
        )
        public_msg = (
            str(exc) if (DEV_MODE or current_app.debug)
            else 'Failed to run GIS component'
        )
        abort(500, message=public_msg)
    except Exception as exc:
        logger.exception(
            'gis_component_run_unhandled_exception',
            extra={
                'component_name': component_name,
                'mode': mode,
                'fsa': fsa,
            },
        )
        public_msg = (
            str(exc) if (DEV_MODE or current_app.debug)
            else 'Failed to run GIS component'
        )
        abort(500, message=public_msg)

    response_data = _result_to_response(result)
    logger.info(
        'gis_component_run_succeeded',
        extra={
            'component_name': result.component_name,
            'mode': result.mode.value,
            'fsa': result.fsa,
            'workflow_output_path': result.workflow_output_path,
            'standardized_output_path': result.standardized_output_path,
            'cleaned_output_paths': list(result.cleaned_output_paths),
        },
    )
    return response_data


@blp.route('/components/<string:component_name>/runs')
class GISComponentRuns(MethodView):
    """Runs a configured GIS component."""

    @blp.arguments(GISComponentRunRequestSchema)
    @blp.response(201, GISComponentRunResultSchema)
    def post(self, request_data, component_name):
        return _run_gis_component(component_name, request_data)


def _submit_fsa_batch(component_name, request_data):
    mode = request_data['mode']
    all_fsas = request_data['all_fsas']
    requested_fsas = request_data.get('fsas')
    try:
        runner = FsaBatchRunner(
            component_name=component_name,
            mode=mode,
            max_workers=request_data['max_workers'],
            non_null_required_fields=request_data.get('drop_null_fields'),
            cleanup_outputs=request_data['cleanup_outputs'],
            keep_outputs=request_data.get('keep_outputs'))
        runner.validate_component()
        if requested_fsas is not None:
            requested_fsas = normalize_fsas(requested_fsas)
    except GisComponentNotFoundError as exc:
        abort(404, message=str(exc))
    except GisComponentContractError as exc:
        abort(422, message=str(exc))
    except (TypeError, ValueError) as exc:
        abort(400, message=str(exc))

    job = get_batch_job_store().create_job(
        component_name=runner.component_name,
        mode=runner.mode,
        requested_fsas=requested_fsas,
        all_fsas=all_fsas,
        max_workers=runner.max_workers,
        non_null_required_fields=runner.non_null_required_fields,
        cleanup_outputs=runner.cleanup_outputs,
        keep_outputs=runner.keep_outputs)
    logger.info(
        'fsa_batch_submitted',
        extra={
            'batch_id': job.batch_id,
            'component_name': job.component_name,
            'all_fsas': job.all_fsas,
            'max_workers': job.max_workers,
        })
    return _batch_to_response(job)


@blp.route('/components/<string:component_name>/batch-runs')
class GISComponentBatchRuns(MethodView):
    """Submit an asynchronous batch for an FSA-capable component."""

    @blp.arguments(FsaBatchRunRequestSchema)
    @blp.response(202, FsaBatchJobSchema)
    def post(self, request_data, component_name):
        return _submit_fsa_batch(component_name, request_data)


@blp.route(
    '/components/<string:component_name>/batch-runs/<string:batch_id>')
class GISComponentBatchRunStatus(MethodView):
    """Return persistent progress and results for an FSA batch job."""

    @blp.response(200, FsaBatchJobSchema)
    def get(self, component_name, batch_id):
        job = get_batch_job_store().get_job(
            batch_id,
            component_name=component_name)
        if job is None:
            abort(404, message=f'FSA batch job not found: {batch_id}')
        return _batch_to_response(job)


@blp.route('/artifacts/<string:artifact_id>/download')
class GISArtifactDownload(MethodView):
    """Download a registered standardized output without executing GIS."""

    @blp.response(200, schema={'type': 'string', 'format': 'binary'},
                  content_type='application/geo+json')
    @blp.alt_response(404, description='Unknown or malformed artifact ID.')
    @blp.alt_response(410, description='Registered artifact copy is unavailable.')
    @blp.alt_response(500, description='Artifact store or read failure.')
    def get(self, artifact_id):
        try:
            artifact, stream = get_artifact_store().open_download(artifact_id)
        except ArtifactNotFoundError as exc:
            abort(404, message=str(exc))
        except ArtifactUnavailableError as exc:
            abort(410, message=str(exc))
        except ArtifactError:
            logger.exception('artifact_download_failed', extra={'artifact_id': artifact_id})
            abort(500, message='Failed to read artifact.')
        try:
            response = send_file(
                stream,
                mimetype='application/geo+json',
                as_attachment=True,
                download_name=f'{artifact.artifact_id}.geojson',
                etag=artifact.sha256)
            response.content_length = artifact.size_bytes
            response.call_on_close(stream.close)
        except Exception:
            stream.close()
            raise
        logger.info('artifact_download', extra={'artifact_id': artifact.artifact_id})
        return response
