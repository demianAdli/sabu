"""
Sabu project
jug_sim_buildings package
workflow module
Run scenario_001 through the preprocessing and uniquification APIs.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import json

from sabu_chassis.logging import get_logger
from sabu_chassis.logging.context import get_request_id, set_request_id

from ..http_transport import HTTPTransport
from .contracts import (
    AREA_KEY, IDENTIFIER_KEY, load_json, validate_input,
    validate_preprocessing, validate_uniquification,
)
from .reporting import duplicate_report, source_record, summary_text
from .run_artifacts import RunArtifacts, file_digest, utc_now


logger = get_logger(__name__)


class ScenarioRunError(RuntimeError):
    """A failed run retains evidence in its directory."""

    def __init__(self, directory, stage, error):
        self.directory = directory
        self.stage = stage
        super().__init__(f'scenario_001 failed at {stage}: {error}; run directory: {directory}')


def run_scenario(config, *, transport=None, run_id=None):
    """Run synchronously; injected transports remain owned by the caller."""
    artifacts = RunArtifacts(config.output_root, run_id)
    previous_id = get_request_id()
    set_request_id(artifacts.run_id)
    state = {
        'scenario': 'scenario_001', 'run_id': artifacts.run_id,
        'request_id': artifacts.run_id, 'parent_request_id': previous_id,
        'started_at': utc_now(), 'status': 'running', 'stage': 'initializing',
        'configuration': config.as_dict(), 'artifacts': {},
        'contract_notes': [
            'Generic standardized GeoJSON schema differs from Montreal adapter fields.',
            'CRS is not guaranteed; preserve declarations, otherwise record unknown.',
            'Uniquification omits top-level IDs; join source_records by run_id/input_position.',
        ],
    }
    client = transport
    primary_error = None
    secondary_errors = []

    def stage(name):
        state['stage'] = name
        artifacts.write_json('run.json', state)
        logger.info('scenario_stage', extra={'run_id': artifacts.run_id, 'stage': name})

    def remember(relative):
        state['artifacts'][relative] = file_digest(artifacts.path(relative))

    try:
        artifacts.write_json('run.json', state)
        if client is None:
            client = HTTPTransport()

        stage('preprocessing')
        request_path = artifacts.write_json('requests/preprocessing.json', config.preprocessing_request())
        client.exchange(
            'POST', f'{config.gis_cities_url}/components/mtl_fsa_gisoo/runs',
            destination=artifacts.path('responses/preprocessing.body'),
            metadata_path=artifacts.path('responses/preprocessing.http.json'),
            run_id=artifacts.run_id, timeout=config.timeout('preprocess'),
            expected_status=201, body_path=request_path)
        stage('preprocessing_contract')
        result = load_json(artifacts.path('responses/preprocessing.body'))
        download_url = validate_preprocessing(result, config)
        state['upstream_artifact'] = {
            'id': result['standardized_artifact_id'], 'download_url': download_url,
            'cleaned_output_paths': result['cleaned_output_paths'],
        }
        remember('responses/preprocessing.body')

        stage('download')
        client.exchange(
            'GET', download_url, destination=artifacts.temporary('download.part'),
            metadata_path=artifacts.path('responses/download.http.json'),
            run_id=artifacts.run_id, timeout=config.timeout('download'), expected_status=200)
        # A complete but invalid GeoJSON is still preserved as the downloaded input.
        input_path = artifacts.promote_download()
        remember('input/standardized.geojson')
        stage('input_contract')
        collection = load_json(input_path)
        crs = {
            'status': 'declared' if isinstance(collection, dict) and 'crs' in collection else 'unknown',
            'declaration': collection.get('crs') if isinstance(collection, dict) else None,
            'source': 'input/standardized.geojson',
            'note': 'Declaration copied verbatim, not verified. Absence is not evidence of EPSG:4326.',
            'coordinates_transformed': False,
        }
        artifacts.write_json('source_crs.json', crs)
        input_features = validate_input(collection)
        artifacts.write_json_lines('source_records.jsonl', (
            source_record(artifacts.run_id, position, feature)
            for position, feature in enumerate(input_features)))
        remember('source_records.jsonl')

        stage('uniquification')
        request_path = artifacts.temporary('uniquification-request.json')
        # Preparation scratch is only request serialization, not LCA preparation.
        with request_path.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump({'buildings_set': collection, 'unique_attribute_key': IDENTIFIER_KEY,
                       'area_key': AREA_KEY}, stream, ensure_ascii=False, allow_nan=False)
        artifacts.write_json('requests/uniquification.json', {
            'unique_attribute_key': IDENTIFIER_KEY, 'area_key': AREA_KEY,
            'buildings_set_artifact': 'input/standardized.geojson',
            'buildings_set_sha256': state['artifacts']['input/standardized.geojson']['sha256'],
            'serialized_request': file_digest(request_path),
        })
        client.exchange(
            'POST', f'{config.gis_validation_url}/uniquifications',
            destination=artifacts.path('responses/uniquification.body'),
            metadata_path=artifacts.path('responses/uniquification.http.json'),
            run_id=artifacts.run_id, timeout=config.timeout('uniquification'),
            expected_status=200, body_path=request_path)
        stage('uniquification_contract')
        result = load_json(artifacts.path('responses/uniquification.body'))
        stats, records, _ = validate_uniquification(result, input_features)

        stage('preserving_results')
        for name, value in (
                ('retained.geojson', result['retained_geojson']),
                ('statistics.json', stats), ('records.json', records)):
            artifacts.write_json(name, value)
            remember(name)
        state['counts'] = stats
        stage('reporting')
        artifacts.write_json('reports/duplicates.json', duplicate_report(records, input_features))
        artifacts.write_text('reports/summary.md', summary_text(artifacts.run_id, config.fsa, stats, crs))
        for name in ('responses/uniquification.body', 'source_crs.json',
                     'reports/duplicates.json', 'reports/summary.md'):
            remember(name)
        state['status'] = 'succeeded'
        state['stage'] = 'completed'
    except (Exception, KeyboardInterrupt) as exc:
        primary_error = exc
        state['status'] = 'failed'
        state['error'] = {'type': type(exc).__name__, 'message': str(exc), 'stage': state['stage']}
        logger.exception('scenario_failed', extra={'run_id': artifacts.run_id, 'stage': state['stage']})
    finally:
        if transport is None and client is not None:
            try:
                client.close()
            except Exception as exc:
                secondary_errors.append({'operation': 'close_transport', 'message': str(exc)})
        try:
            secondary_errors.extend(artifacts.cleanup(failed=primary_error is not None))
        except Exception as exc:
            secondary_errors.append({'operation': 'cleanup', 'message': str(exc)})
        state['cleanup_errors'] = secondary_errors
        if secondary_errors:
            logger.error('scenario_cleanup_errors', extra={
                'run_id': artifacts.run_id, 'cleanup_errors': secondary_errors})
            if primary_error is None:
                state['status'] = 'succeeded_with_cleanup_errors'
        state['finished_at'] = utc_now()
        try:
            artifacts.write_json('run.json', state)
        except Exception as exc:
            logger.exception('scenario_metadata_finalization_failed', extra={'run_id': artifacts.run_id})
            if primary_error is None:
                primary_error = exc
            # Best effort fallback without masking the original processing failure.
            state['status'] = 'failed'
            state.setdefault('error', {'type': type(exc).__name__, 'message': str(exc),
                                       'stage': 'finalizing_metadata'})
            state['metadata_error'] = str(exc)
            try:
                secondary_errors.extend(artifacts.cleanup(failed=True))
            except Exception as cleanup_error:
                secondary_errors.append({'operation': 'finalization_cleanup',
                                         'message': str(cleanup_error)})
            try:
                artifacts.path('evidence/finalization.json').write_text(
                    json.dumps(state, indent=2, allow_nan=False) + '\n', encoding='utf-8')
            except Exception:
                logger.exception('scenario_failure_evidence_unavailable')
        finally:
            try:
                if primary_error is None:
                    logger.info('scenario_completed', extra={
                        'run_id': artifacts.run_id, 'status': state['status']})
            finally:
                set_request_id(previous_id)
    if primary_error is not None:
        raise ScenarioRunError(artifacts.directory, state['error']['stage'], primary_error) from primary_error
    return {'run_id': artifacts.run_id, 'run_directory': str(artifacts.directory),
            'status': state['status'], 'counts': state['counts']}
