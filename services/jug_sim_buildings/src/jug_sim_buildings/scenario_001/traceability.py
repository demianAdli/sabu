"""
Sabu project
jug_sim_buildings package
traceability module
Consolidate scenario record histories without attributing duplicate carbon.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import json
from pathlib import Path

from .contracts import load_json, require
from .run_artifacts import file_digest


def json_lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def write_trace(artifacts, state):
    """Write incomplete histories on failure and require complete joins on success."""
    source_path = artifacts.path('source_records.jsonl')
    sources = json_lines(source_path) if source_path.exists() else []
    records_path = artifacts.path('records.json')
    records = load_json(records_path) if records_path.exists() else []
    require(not records or len(records) == len(sources), 'Trace source/uniquification count mismatch.')
    mappings, results, excluded, submitted = {}, {}, {}, set()
    preparation = state.get('preparation')
    attempt = Path(preparation['preparation_directory']) if preparation else None
    if attempt is None and state.get('error', {}).get('stage') == 'preparation':
        candidates = list((artifacts.directory / 'preparation').glob('*/preparation.json'))
        if len(candidates) == 1:
            attempt = candidates[0].parent
    if attempt is not None:
        require(attempt.is_relative_to(artifacts.directory / 'preparation') and attempt.resolve() == attempt,
                'Trace preparation outside current run.')
        path = attempt / 'id_mappings.jsonl'
        if path.exists():
            entries = json_lines(path)
            metadata = load_json(attempt / 'preparation.json')
            digest = metadata.get('artifacts', {}).get('id_mappings.jsonl')
            if digest is not None:
                require(file_digest(path) == digest, 'Trace preparation mappings changed.')
            mappings = {m['retained_feature_index']: m for m in entries}
            require(len(mappings) == len(entries), 'Trace duplicate retained positions.')
            require(len({m['prepared_id'] for m in entries}) == len(entries), 'Trace duplicate prepared IDs.')
            retained_count = sum(r['status'] == 'retained' for r in records)
            require(len(entries) == retained_count, 'Trace retained/preparation count mismatch.')
            accepted = sum(m['status'] == 'accepted' for m in entries)
            rejected = sum(m['status'] == 'rejected' for m in entries)
            require(accepted + rejected == retained_count, 'Trace retained partition mismatch.')
            require(all(metadata.get('counts', {}).get(key) == value for key, value in (
                ('retained_input', retained_count), ('accepted', accepted), ('rejected', rejected))),
                'Trace preparation statistics disagree.')
    request = artifacts.path('requests/lca.json')
    if request.exists():
        submitted_ids = load_json(request)['submitted_ids']
        require(len(set(submitted_ids)) == len(submitted_ids), 'Trace duplicate submitted IDs.')
        submitted = set(submitted_ids)
        require(submitted == {m['prepared_id'] for m in mappings.values() if m['status'] == 'accepted'},
                'Trace submitted/accepted ID mismatch.')
    result_path = artifacts.path('lca/results.json')
    exclusion_path = artifacts.path('lca/exclusions.json')
    if exclusion_path.exists():
        values = load_json(exclusion_path)
        require(all(isinstance(row, dict) and type(row.get('feature_id')) is int for row in values), 'Invalid trace LCA exclusions.')
        excluded = {row['feature_id']: {'exclusion_index': index, 'exclusion': row} for index, row in enumerate(values)}
        require(len(excluded) == len(values) and set(excluded) <= submitted, 'Trace exclusion ID mismatch.')
    if result_path.exists():
        values = load_json(result_path)
        results = {r['feature_id']: index for index, r in enumerate(values)}
        require(len(results) == len(values) and not set(results) & set(excluded)
                and set(results) | set(excluded) == submitted, 'Trace result/exclusion ID mismatch.')
    rows = []
    for position, source in enumerate(sources):
        require(source['input_position'] == position and source['run_id'] == artifacts.run_id,
                'Trace source identity mismatch.')
        record = records[position] if records else None
        row = {'run_id': artifacts.run_id, 'input_position': position,
               'record_ref': source['record_ref'], 'source': source,
               'uniquification': record, 'preparation': None, 'lca': None}
        if record:
            require(record['input_position'] == position and record['record_ref'] == source['record_ref'],
                    'Trace uniquification reference mismatch.')
            mapping = mappings.get(record['retained_feature_index'])
            if mapping:
                require(mapping['winner_record_ref'] == record['retained_record_ref'], 'Trace winner mismatch.')
                members = {m['input_position']: m for m in mapping['input_records']}
                require(len(members) == len(mapping['input_records']) and position in members,
                        'Trace preparation member mismatch.')
                require(members[position]['source'] == source and members[position]['record_ref'] == source['record_ref'],
                        'Trace preparation source mismatch.')
                row['preparation'] = {'prepared_id': mapping['prepared_id'], 'status': mapping['status'],
                                      'errors': mapping['errors'], 'normalizations': mapping['normalizations'],
                                      'applies_to': 'self' if record['status'] == 'retained' else 'retained_representative'}
                identifier = mapping['prepared_id']
                if record['status'] == 'retained' and identifier in submitted:
                    row['lca'] = {'submitted_id': identifier,
                                  'status': 'result_received' if identifier in results else 'excluded' if identifier in excluded else 'unresolved',
                                  'result_index': results.get(identifier),
                                  'result_artifact': 'lca/results.json' if identifier in results else None}
                    if identifier in excluded:
                        row['lca'].update(exclusion_artifact='lca/exclusions.json', **excluded[identifier])
        rows.append(row)
    if mappings:
        all_members = [member['input_position'] for mapping in mappings.values() for member in mapping['input_records']]
        require(sorted(all_members) == list(range(len(sources))), 'Trace preparation members do not partition input.')
    if state.get('lca', {}).get('status') == 'succeeded':
        require(sum(row['lca'] is not None for row in rows) == len(submitted) == len(results) + len(excluded),
                'Trace does not account for every submitted building.')
    artifacts.write_json_lines('trace/records.jsonl', rows)
    summary = {'standardized_records': len(sources), 'uniquification_decisions': len(records),
               'preparation_decisions': len(mappings), 'submitted_records': len(submitted),
               'identified_results': len(results), 'lca_exclusions': len(excluded),
               'unresolved_submissions': len(submitted - results.keys() - excluded.keys()),
               'status': 'complete' if state.get('lca', {}).get('status') == 'succeeded' or (
                   bool(submitted) and result_path.exists() and submitted == set(results) | set(excluded)) else 'partial',
               'note': 'Removed records link to a representative; carbon is counted only for submitted retained records.'}
    artifacts.write_json('trace/reconciliation.json', summary)
    return summary
