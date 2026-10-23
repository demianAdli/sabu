"""
Sabu project
jug_sim_buildings package
preparation module
Prepare traceable eligible LCA inputs in separate run attempts.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from collections import Counter
import json
from pathlib import Path

from sabu_chassis.logging import get_logger
from sabu_chassis.logging.context import get_request_id, set_request_id

from .contracts import load_json, require, validate_uniquification
from .lca_contract import SCENARIO_RULES, normalize_feature
from .prepared_identity import assign_identities
from .reporting import source_record
from .reprojection import CityGISOOReprojector, verify_final
from .run_artifacts import PreparationArtifacts, file_digest, utc_now


logger = get_logger(__name__)
INPUTS = ('input/standardized.geojson', 'retained.geojson', 'records.json',
          'source_records.jsonl', 'source_crs.json', 'statistics.json')


class PreparationError(RuntimeError):
    def __init__(self, directory, error):
        self.directory = directory
        super().__init__(f'LCA preparation failed: {error}; attempt directory: {directory}')


def _load_run(directory, config, allow_running):
    state = load_json(directory / 'run.json')
    require(state.get('scenario') == 'scenario_001', 'Not a scenario_001 run.')
    fsa = state.get('fsa', state.get('configuration', {}).get('fsa'))
    require(fsa == config.fsa, 'Configured FSA differs from the saved run.')
    require(state.get('status') in ('succeeded', 'succeeded_with_cleanup_errors') or (
        state.get('status') == 'failed' and state.get('error', {}).get('stage') == 'preparation') or (
        allow_running and state.get('status') == 'running' and state.get('stage') == 'preparation'),
        'Run has not completed uniquification successfully.')
    require(state.get('run_id') == directory.name, 'Run ID and directory disagree.')
    for relative in INPUTS:
        path = directory / relative
        require(path.resolve() == path, f'Redirected input artifact: {relative}.')
        digest = state.get('artifacts', {}).get(relative)
        require(digest is not None and file_digest(path) == digest, f'Artifact hash mismatch: {relative}.')
    original = load_json(directory / 'input/standardized.geojson')
    retained = load_json(directory / 'retained.geojson')
    records = load_json(directory / 'records.json')
    stats = load_json(directory / 'statistics.json')
    validate_uniquification({'uniquification': stats, 'records': records,
                            'retained_geojson': retained}, original['features'])
    with (directory / 'source_records.jsonl').open(encoding='utf-8') as stream:
        sources = [json.loads(line) for line in stream]
    require(len(sources) == len(original['features']), 'Source mapping count mismatch.')
    for position, (feature, source) in enumerate(zip(original['features'], sources)):
        require(source == source_record(state['run_id'], position, feature), 'Source mapping mismatch.')
    crs = load_json(directory / 'source_crs.json')
    require(crs.get('source') == 'input/standardized.geojson', 'Unknown CRS evidence source.')
    return state, original, retained, records, sources, crs


def prepare_run(run_directory, config, *, reprojector=None, allow_running=False):
    """Prepare a saved run without HTTP calls or rewriting any existing run artifacts."""
    directory = Path(run_directory).resolve()
    artifacts = PreparationArtifacts(directory)
    previous = get_request_id()
    backend = reprojector
    error = None
    metadata = {'attempt_id': artifacts.attempt_id, 'status': 'running', 'stage': 'lineage',
                'started_at': utc_now(), 'configuration': config.as_dict(),
                'scenario_rules_beyond_lca_schema': SCENARIO_RULES, 'artifacts': {}}

    def stage(name):
        metadata['stage'] = name
        artifacts.write_json('preparation.json', metadata)
        logger.info('preparation_stage', extra={'stage': name, 'fsa': config.fsa,
                                              'attempt_id': artifacts.attempt_id})

    try:
        state, original, retained, records, sources, crs_evidence = _load_run(
            directory, config, allow_running)
        set_request_id(state['run_id'])
        metadata.update({'run_id': state['run_id'], 'fsa': config.fsa,
                         'input_artifacts': {k: state['artifacts'][k] for k in INPUTS}})
        stage('crs_and_capability')
        if backend is None:
            backend = CityGISOOReprojector()
        crs_report = backend.resolve_crs([
            ('original_geojson', original.get('crs')),
            ('source_crs_sidecar', crs_evidence.get('declaration')),
            ('retained_geojson', retained.get('crs'))], config)
        artifacts.write_json('crs.json', crs_report)
        measurement_audit = {
            'configured_projected_option': config.preparation_measurement_crs,
            'existing_metric_fields': ['citygisoo_area', 'nrcan_building_area', 'roll_area',
                                       'usage_area', 'main_floor_area'],
            'metrics_recomputed': False, 'geometry_processing': 'eligibility checks only; no repair',
            'inspected_upstream_method': 'GeoPackageFeatureProcessor.add_area_field uses QgsDistanceArea '
                                         'with layer CRS and project ellipsoid (WGS84 fallback).',
            'warnings': ['Historical ellipsoid/operation provenance is not recorded in these run artifacts.',
                         'Existing metrics must not be described as EPSG:2950 planar measurements.',
                         'Final reprojection cannot correct earlier measurements; supplied values are unchanged.']}
        artifacts.write_json('measurement_audit.json', measurement_audit)
        for warning in measurement_audit['warnings']:
            logger.warning('preparation_measurement_warning', extra={
                'fsa': config.fsa, 'warning': warning, 'attempt_id': artifacts.attempt_id})
        stage('eligibility')
        prepared, mappings = assign_identities(retained['features'], records, sources,
                                               fsa=config.fsa, run_id=state['run_id'])
        accepted, rejected, reasons = [], [], Counter()
        for index, (feature, mapping) in enumerate(zip(prepared, mappings)):
            normalized, errors, changes = normalize_feature(feature)
            if not any(e['field'] == 'geometry' for e in errors):
                geometry_error = backend.geometry_error(normalized['geometry'])
                if geometry_error:
                    errors.append({'field': 'geometry', 'reason': geometry_error})
            mapping.update({'attempt_id': artifacts.attempt_id, 'normalizations': changes,
                            'status': 'rejected' if errors else 'accepted', 'errors': errors})
            if errors:
                rejected.append(retained['features'][index])
                reasons.update(e['field'] for e in errors)
            else:
                accepted.append(normalized)
        counts = {'retained_input': len(prepared), 'accepted': len(accepted),
                  'rejected': len(rejected), 'offending_fields': dict(reasons)}
        require(counts['retained_input'] == counts['accepted'] + counts['rejected'] == len(mappings),
                'Retained = accepted + rejected reconciliation failed.')
        require(len({m['prepared_id'] for m in mappings}) == len(mappings), 'Prepared ID collision.')
        metadata['counts'] = counts
        artifacts.write_json('accepted.source.geojson', {
            'type': 'FeatureCollection', 'crs': {'type': 'name', 'properties': {
                'name': crs_report['source_crs']}}, 'features': accepted})
        artifacts.write_json('rejected.geojson', {
            'type': 'FeatureCollection', 'crs': {'type': 'name', 'properties': {
                'name': crs_report['source_crs']}}, 'features': rejected})
        artifacts.write_json_lines('id_mappings.jsonl', mappings)
        artifacts.write_json('rejections.json', [m for m in mappings if m['status'] == 'rejected'])
        artifacts.write_json('statistics.json', counts)
        require(bool(accepted), 'No eligible records remain; inspect rejections.json.')
        stage('reprojection_and_export')
        for name in ('geometry-source.geojson', 'geometry-wgs84.geojson'):
            artifacts.temporary(name)
        final = artifacts.temporary('lca-final.geojson')
        backend.transform(accepted, crs_report, final, artifacts.path('tmp'),
                          config.preparation_coordinate_operation)
        exported = load_json(final)
        require(exported.get('type') == 'FeatureCollection' and 'crs' not in exported,
                'Final export must be WGS84 GeoJSON without a legacy CRS member.')
        verify_final(exported['features'], accepted, equivalent=crs_report['status'] == 'copied')
        # Publish only after verification, never overwrite a previous attempt.
        destination = artifacts.path('lca_input.geojson')
        require(not destination.exists(), 'Final artifact already exists.')
        final.replace(destination)
        crs_report['output_location'] = str(destination)
        artifacts.write_json('crs.json', crs_report)
        artifacts.write_text('summary.md',
            f'# LCA preparation: {config.fsa}\n\nRetained: {len(prepared)}; accepted: '
            f'{len(accepted)}; rejected: {len(rejected)}.\n\n'
            f'CRS: {crs_report["source_crs"]} → EPSG:4326 (longitude/latitude). '
            f'Status: {crs_report["status"]}. Metrics unchanged.\n')
        for name in ('accepted.source.geojson', 'rejected.geojson', 'id_mappings.jsonl',
                     'rejections.json', 'statistics.json', 'measurement_audit.json',
                     'crs.json', 'lca_input.geojson', 'summary.md'):
            metadata['artifacts'][name] = file_digest(artifacts.path(name))
        metadata.update(status='succeeded', stage='completed')
    except (Exception, KeyboardInterrupt) as exc:
        error = exc
        metadata.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
        logger.exception('preparation_failed', extra={'fsa': config.fsa,
                         'attempt_id': artifacts.attempt_id, 'output_location': str(artifacts.directory)})
    finally:
        secondary = []
        if reprojector is None and backend is not None:
            try:
                backend.close()
            except Exception as exc:
                secondary.append({'operation': 'close_reprojector', 'message': str(exc)})
        try:
            secondary.extend(artifacts.cleanup(failed=error is not None))
        except Exception as exc:
            secondary.append({'operation': 'cleanup', 'message': str(exc)})
        metadata['cleanup_errors'] = secondary
        metadata['finished_at'] = utc_now()
        if secondary:
            logger.error('preparation_cleanup_errors', extra={'errors': secondary})
            if error is None:
                metadata['status'] = 'succeeded_with_cleanup_errors'
        try:
            artifacts.write_json('preparation.json', metadata)
        except Exception as exc:
            if error is None:
                error = exc
            logger.exception('preparation_metadata_failure')
            try:
                secondary.extend(artifacts.cleanup(failed=True))
            except Exception as cleanup_error:
                secondary.append({'operation': 'finalization_cleanup', 'message': str(cleanup_error)})
            try:
                metadata.update(status='failed', metadata_error=str(exc))
                artifacts.path('evidence/finalization.json').write_text(
                    json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
            except Exception:
                logger.exception('preparation_evidence_unavailable')
        finally:
            set_request_id(previous)
    if error is not None:
        raise PreparationError(artifacts.directory, error) from error
    return {'run_id': state['run_id'], 'fsa': config.fsa, 'attempt_id': artifacts.attempt_id,
            'status': metadata['status'], 'preparation_directory': str(artifacts.directory),
            'lca_input_path': str(artifacts.path('lca_input.geojson')), 'counts': counts}
