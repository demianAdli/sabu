"""
Sabu project
jug_sim_buildings package
contracts module
Check scenario API structures and reconcile positional provenance.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import json
import re
from urllib.parse import urlsplit

from .config import http_url


IDENTIFIER_KEY = 'roll_provincial_id'
AREA_KEY = 'citygisoo_area'
REASONS = {
    'missing_identifier', 'unique_identifier', 'largest_area',
    'earliest_maximum_area', 'smaller_area', 'later_tied_maximum',
}


class ContractError(ValueError):
    """An upstream response cannot safely be used by the next stage."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def load_json(path):
    def reject_constant(value):
        raise ContractError(f'Non-finite JSON constant: {value}.')

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f'Duplicate JSON object key: {key}.')
            result[key] = value
        return result

    try:
        with path.open(encoding='utf-8-sig') as stream:
            return json.load(stream, parse_constant=reject_constant, object_pairs_hook=unique_keys)
    except (ValueError, UnicodeError) as exc:
        raise ContractError(f'Invalid JSON in {path.name}: {exc}') from exc


def validate_preprocessing(result, config):
    require(isinstance(result, dict), 'Preprocessing response must be an object.')
    require(result.get('component_name') == 'mtl_fsa_gisoo', 'Unexpected component_name.')
    require(result.get('mode') == 'standardize', 'Unexpected preprocessing mode.')
    require(result.get('fsa') == config.fsa, 'Unexpected preprocessing FSA.')
    for key in ('workflow_output_path', 'standardized_output_path'):
        require(isinstance(result.get(key), str) and bool(result[key].strip()), f'Missing {key}.')
    cleaned = result.get('cleaned_output_paths')
    require(isinstance(cleaned, list) and all(isinstance(p, str) for p in cleaned),
            'Invalid cleaned_output_paths.')
    artifact_id = result.get('standardized_artifact_id')
    require(isinstance(artifact_id, str) and bool(re.fullmatch(r'[0-9a-f]{32}', artifact_id)),
            'Missing or invalid standardized_artifact_id.')
    try:
        url = http_url(result.get('standardized_download_url'))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ContractError('Missing or invalid standardized_download_url.') from exc
    actual, base = urlsplit(url), urlsplit(config.gis_cities_url)

    def origin(parsed):
        return (parsed.scheme, parsed.hostname,
                parsed.port or (443 if parsed.scheme == 'https' else 80))

    require(origin(actual) == origin(base),
            'Artifact URL origin differs from configured GIS Cities URL; check proxy configuration.')
    require(actual.path == f'{base.path.rstrip("/")}/artifacts/{artifact_id}/download',
            'Artifact URL path does not match its registered ID and API prefix.')
    return url


def features(collection):
    require(isinstance(collection, dict) and collection.get('type') == 'FeatureCollection',
            'Expected a GeoJSON FeatureCollection.')
    values = collection.get('features')
    require(isinstance(values, list), 'GeoJSON features must be an array.')
    for position, feature in enumerate(values):
        require(isinstance(feature, dict) and feature.get('type') == 'Feature',
                f'Invalid feature at position {position}.')
        require(isinstance(feature.get('properties'), dict),
                f'Invalid properties at position {position}.')
        require('geometry' in feature and (
            feature['geometry'] is None or isinstance(feature['geometry'], dict)),
            f'Invalid geometry at position {position}.')
    return values


def validate_input(collection):
    values = features(collection)
    # Match loaded-column requirements: null values are allowed and never dropped.
    columns = {key for feature in values for key in feature['properties']}
    require({IDENTIFIER_KEY, AREA_KEY} <= columns,
            'Downloaded input is missing required uniquification columns '
            '(an empty collection also has no loadable columns).')
    return values


def validate_uniquification(result, input_features):
    require(isinstance(result, dict), 'Uniquification response must be an object.')
    stats = result.get('uniquification')
    records = result.get('records')
    retained = features(result.get('retained_geojson'))
    require(isinstance(stats, dict), 'Missing uniquification statistics.')
    require(stats.get('applied') is True and stats.get('unique_attribute_key') == IDENTIFIER_KEY
            and stats.get('ranking_area_key') == AREA_KEY, 'Unexpected uniquification settings.')
    for key in ('input_features', 'retained_features', 'removed_features', 'duplicate_groups'):
        require(type(stats.get(key)) is int and stats[key] >= 0, f'Invalid {key} count.')
    count = len(input_features)
    require(stats['input_features'] == count, 'Input count differs from downloaded input.')
    require(count == stats['retained_features'] + stats['removed_features'],
            'Input = retained + removed reconciliation failed.')
    require(stats['retained_features'] == len(retained), 'Retained GeoJSON count mismatch.')
    require(isinstance(records, list) and len(records) == count, 'Record mapping count mismatch.')
    winners = {}
    for position, record in enumerate(records):
        require(isinstance(record, dict), 'Record mapping must be an object.')
        require(type(record.get('input_position')) is int and record['input_position'] == position
                and record.get('record_ref') == f'record:{position}', 'Invalid input-position mapping.')
        require(record.get('status') in ('retained', 'removed'), 'Invalid record status.')
        require(record.get('reason') in REASONS, 'Invalid record reason.')
        index = record.get('retained_feature_index')
        require(type(index) is int and 0 <= index < len(retained), 'Invalid retained feature index.')
        ref = record.get('retained_record_ref')
        require(isinstance(ref, str) and bool(re.fullmatch(r'record:[0-9]+', ref)),
                'Invalid retained record reference.')
        require('identifier' in record and 'area' in record, 'Missing record identifier or area.')
        properties = input_features[position]['properties']
        require(record['identifier'] == properties.get(IDENTIFIER_KEY)
                and record['area'] == properties.get(AREA_KEY), 'Record source values mismatch.')
        if record['status'] == 'retained':
            require(ref == record['record_ref'], 'Retained record must map to itself.')
            require(index == len(winners), 'Retained features must preserve input order.')
            winners[record['record_ref']] = record
            # GeoPandas may fill absent properties with null; feature IDs are dropped.
            require(retained[index]['geometry'] == input_features[position]['geometry'],
                    'Retained geometry differs from its source record.')
            returned = retained[index]['properties']
            require(all(returned.get(k) == v for k, v in properties.items())
                    and all(k in properties or v is None for k, v in returned.items()),
                    'Retained properties differ from their source record.')
    require(len(winners) == stats['retained_features'], 'Retained record count mismatch.')
    require(sum(r['status'] == 'removed' for r in records) == stats['removed_features'],
            'Removed record count mismatch.')
    removal_groups = set()
    identifier_winners = {}
    for record in records:
        winner = winners.get(record['retained_record_ref'])
        require(winner is not None, 'Record points to a missing or removed winner.')
        require(record['retained_feature_index'] == winner['retained_feature_index'],
                'Winner index mismatch.')
        identifier = record['identifier']
        missing = identifier is None or (isinstance(identifier, str) and not identifier.strip())
        if missing:
            require(record['status'] == 'retained', 'Missing identifiers must remain independent.')
        else:
            try:
                previous = identifier_winners.setdefault(identifier, record['retained_record_ref'])
            except TypeError as exc:
                raise ContractError('Unusable non-scalar identifier in record mapping.') from exc
            require(previous == record['retained_record_ref'],
                    'One identifier maps to multiple retained winners.')
        if record['status'] == 'removed':
            require(record['identifier'] == winner['identifier']
                    and record['identifier'] is not None
                    and not (isinstance(record['identifier'], str)
                             and not record['identifier'].strip()), 'Invalid duplicate winner mapping.')
            removal_groups.add(record['retained_record_ref'])
    require(len(removal_groups) == stats['duplicate_groups'], 'Duplicate group count mismatch.')
    return stats, records, retained
