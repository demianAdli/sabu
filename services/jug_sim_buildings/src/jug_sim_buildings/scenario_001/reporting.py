"""
Sabu project
jug_sim_buildings package
reporting module
Report selection, preparation and identified LCA execution outcomes.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from collections import defaultdict
import math

from .contracts import require


def completion_text(state):
    """Describe exclusions separately from whole-stage processing failures."""
    preparation = state.get('preparation', {}).get('counts', {})
    lca = state.get('lca', {})
    summary = lca.get('summary', {})
    return ('\n## Execution outcome\n\n'
            f'Status: {state["status"]}. Stage: {state["stage"]}.\n\n'
            f'Preparation: {preparation or "not completed; inspect preparation evidence"}.\n\n'
            f'LCA: {lca.get("status", "not completed or not requested")}; '
            f'submitted: {lca.get("submitted", "unknown")}; returned: {lca.get("returned", "unknown")}.\n\n'
            f'Carbon summary: {summary or "unavailable"}.\n\n'
            f'Processing error (not a record exclusion): {state.get("error", "none")}.\n\n'
            'See trace/records.jsonl and reports/evaluation.json for evidence and limitations.\n')


SOURCE_KEYS = (
    'citygisoo_id', 'roll_provincial_id', 'usage_provincial_id',
    'processing_tool', 'processed_by', 'FSA',
)


def source_record(run_id, position, feature):
    return {
        'run_id': run_id, 'input_position': position, 'record_ref': f'record:{position}',
        'feature_id_present': 'id' in feature, 'feature_id': feature.get('id'),
        'source_identifiers': {k: feature['properties'][k] for k in SOURCE_KEYS
                               if k in feature['properties']},
    }


def duplicate_report(records, input_features):
    """Inspect first three groups by first input position; display ten members each."""
    duplicate_refs = {r['retained_record_ref'] for r in records if r['status'] == 'removed'}
    groups = defaultdict(list)
    for record in records:
        if record['retained_record_ref'] in duplicate_refs:
            groups[record['retained_record_ref']].append(record)
    sample = []
    for members in sorted(groups.values(), key=lambda group: group[0]['input_position'])[:3]:
        areas = []
        for member in members:
            try:
                area = float(member['area'])
            except (TypeError, ValueError):
                area = float('nan')
            require(math.isfinite(area), 'Sample duplicate group contains an invalid ranking area.')
            areas.append(area)
        maximum = max(areas)
        expected = members[areas.index(maximum)]
        require(expected['record_ref'] == expected['retained_record_ref'],
                'Sample winner violates greatest-area/earliest-tie policy.')
        displayed = []
        for member in members[:10]:
            feature = input_features[member['input_position']]
            displayed.append({
                **member, 'source_feature_id': feature.get('id'),
                'source_identifiers': {k: feature['properties'][k] for k in SOURCE_KEYS
                                       if k in feature['properties']},
            })
        sample.append({
            'identifier': expected['identifier'], 'member_count': len(members),
            'removed_count': len(members) - 1, 'winner_record_ref': expected['record_ref'],
            'maximum_area': maximum, 'policy_check': 'passed',
            'members': displayed, 'omitted_members': max(0, len(members) - 10),
        })
    return {
        'method': 'First three duplicate groups by first input position; first ten members displayed.',
        'inspection': 'Check all sampled group areas; greatest area wins, earliest input breaks ties.',
        'scope': 'Attribute and positional inspection only; no geographic analysis.',
        'whole_run_duplicate_groups': len(groups), 'sampled_groups': sample,
    }


def summary_text(run_id, fsa, stats, crs):
    return (
        f'# scenario_001 run {run_id}\n\n'
        f'FSA: {fsa}\n\n'
        f'Whole-run input: {stats["input_features"]}\n\n'
        f'Whole-run retained: {stats["retained_features"]}\n\n'
        f'Whole-run removed: {stats["removed_features"]}\n\n'
        f'Duplicate provincial-ID groups: {stats["duplicate_groups"]}\n\n'
        'Input = retained + removed and positional mappings reconciled.\n\n'
        f'Source CRS status: {crs["status"]}. No reprojection was performed.\n\n'
        'See duplicates.json for the bounded sample and records.json for the complete mapping.\n'
    )
