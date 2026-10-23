"""
Sabu project
jug_sim_buildings package
lca_submission module
Submit exact prepared GeoJSON and preserve identified LCA evidence.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from pathlib import Path
import json
import shutil

from .contracts import load_json, require
from .lca_results import carbon_summary, reconcile_results
from .run_artifacts import file_digest


def submit_prepared(artifacts, preparation, config, transport, stage):
    run = artifacts.directory
    attempt = Path(preparation['preparation_directory'])
    require(attempt.is_relative_to(run / 'preparation') and attempt.resolve() == attempt,
            'Preparation must belong to this run without redirected paths.')
    source = attempt / 'lca_input.geojson'
    require(source.resolve() == source, 'Redirected LCA input.')
    metadata = load_json(attempt / 'preparation.json')
    require(metadata.get('status') in ('succeeded', 'succeeded_with_cleanup_errors'), 'Preparation did not succeed.')
    require(metadata.get('run_id') == artifacts.run_id, 'Preparation run identity mismatch.')
    require(metadata.get('fsa') == config.fsa and metadata.get('attempt_id') == attempt.name,
            'Preparation FSA or attempt identity mismatch.')
    digest = file_digest(source)
    require(digest == metadata.get('artifacts', {}).get('lca_input.geojson'), 'Prepared artifact hash mismatch.')
    collection = load_json(source)
    require(collection.get('type') == 'FeatureCollection' and 'crs' not in collection, 'Invalid final GeoJSON representation.')
    crs = load_json(attempt / 'crs.json')
    require(file_digest(attempt / 'crs.json') == metadata['artifacts'].get('crs.json'), 'Preparation CRS report changed.')
    require(crs.get('target_crs') == 'EPSG:4326', 'Final LCA artifact is not verified EPSG:4326.')
    ids = [feature['id'] for feature in collection['features']]
    require(bool(ids) and all(type(i) is int for i in ids) and len(set(ids)) == len(ids), 'Invalid submitted IDs.')
    mappings = [json.loads(line) for line in (attempt / 'id_mappings.jsonl').read_text(encoding='utf-8').splitlines()]
    require(file_digest(attempt / 'id_mappings.jsonl') == metadata['artifacts']['id_mappings.jsonl'], 'Preparation mapping hash mismatch.')
    counts = metadata['counts']
    require(all(m['status'] in ('accepted', 'rejected') for m in mappings), 'Unknown preparation decision.')
    require(len({m['prepared_id'] for m in mappings}) == len(mappings), 'Duplicate prepared identity.')
    require(counts['retained_input'] == counts['accepted'] + counts['rejected'] == len(mappings), 'Preparation count mismatch.')
    require(len(ids) == counts['accepted'] and set(ids) == {m['prepared_id'] for m in mappings if m['status'] == 'accepted'}, 'Accepted ID mismatch.')
    destination = artifacts.path('requests/lca.geojson')
    with destination.open('xb') as output, source.open('rb') as input_stream:
        shutil.copyfileobj(input_stream, output)
    require(file_digest(destination) == digest, 'Submitted copy differs from preparation.')
    artifacts.write_json('requests/lca.json', {
        'preparation_directory': str(attempt.relative_to(run)), 'source': str(source.relative_to(run)),
        'payload': 'requests/lca.geojson', **digest, 'submitted_ids': ids,
        'url': f'{config.lca_url}/emissions', 'identity_contract': 'reader-feature-id-v1',
        'timeout_seconds': [config.lca_connect_timeout_seconds, config.lca_read_timeout_seconds]})
    stage('lca_submission')
    transport.exchange('POST', f'{config.lca_url}/emissions',
                       destination=artifacts.path('responses/lca.body'),
                       metadata_path=artifacts.path('responses/lca.http.json'),
                       run_id=artifacts.run_id,
                       timeout=(config.lca_connect_timeout_seconds, config.lca_read_timeout_seconds),
                       expected_status=201, body_path=destination)
    require(file_digest(destination) == digest and file_digest(source) == digest, 'LCA source or request changed during submission.')
    stage('lca_contract')
    payload = load_json(artifacts.path('responses/lca.body'))
    report, identified = reconcile_results(payload, ids)
    artifacts.write_json('lca/reconciliation.json', report)
    require(report['status'] == 'succeeded', 'Unresolved LCA result reconciliation; inspect lca/reconciliation.json.')
    artifacts.write_json('lca/results.json', payload)
    summary = carbon_summary(identified)
    artifacts.write_json('lca/summary.json', summary)
    return {'status': 'succeeded', 'submitted': len(ids), 'returned': len(payload),
            'summary': summary, 'results_path': 'lca/results.json'}
