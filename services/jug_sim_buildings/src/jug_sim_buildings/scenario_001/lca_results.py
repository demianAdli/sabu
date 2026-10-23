"""
Sabu project
jug_sim_buildings package
lca_results module
Validate identified carbon results and summarize documented units.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import math

from .contracts import require


METRICS = tuple(f'{part}_{stage}_emissions' for stage in ('embodied', 'end_of_life')
                for part in ('opening', 'envelope', 'component'))


def reconcile_results(payload, submitted_ids):
    """Never identify results by their array positions or counts alone."""
    require(isinstance(payload, list), 'LCA response must be an array.')
    require(all(type(i) is int for i in submitted_ids), 'Submitted IDs must be integers.')
    require(len(set(submitted_ids)) == len(submitted_ids), 'Duplicate submitted IDs.')
    identified, issues = {}, []
    for index, result in enumerate(payload):
        if not isinstance(result, dict) or type(result.get('feature_id')) is not int:
            issues.append({'result_index': index, 'reason': 'Missing or invalid feature_id.'})
            continue
        identifier = result['feature_id']
        if identifier in identified:
            issues.append({'result_index': index, 'feature_id': identifier, 'reason': 'Duplicate result ID.'})
            continue
        identified[identifier] = {'result_index': index, 'result': result}
        for field in METRICS:
            value = result.get(field)
            if type(value) not in (int, float) or not math.isfinite(value):
                issues.append({'feature_id': identifier, 'field': field, 'reason': 'Expected finite number.'})
        if all(type(result.get(k)) in (int, float) and math.isfinite(result[k]) for k in METRICS):
            for stage in ('embodied', 'end_of_life'):
                if not math.isclose(result[f'component_{stage}_emissions'],
                                    result[f'opening_{stage}_emissions'] + result[f'envelope_{stage}_emissions'],
                                    rel_tol=1e-9, abs_tol=1e-6):
                    issues.append({'feature_id': identifier, 'reason': f'Inconsistent {stage} subtotal.'})
    missing = sorted(set(submitted_ids) - identified.keys())
    unexpected = sorted(identified.keys() - set(submitted_ids))
    report = {'status': 'failed' if issues or missing or unexpected else 'succeeded',
              'submitted': len(submitted_ids), 'returned': len(payload),
              'missing_ids': missing, 'unexpected_ids': unexpected, 'issues': issues,
              'identity_basis': 'feature_id from reader-created building; never response position'}
    return report, identified


def carbon_summary(identified):
    totals = {key: math.fsum(value['result'][key] for value in identified.values()) for key in METRICS}
    require(all(math.isfinite(v) for v in totals.values()), 'Nonfinite aggregate carbon result.')
    combined = totals['component_embodied_emissions'] + totals['component_end_of_life_emissions']
    require(math.isfinite(combined), 'Nonfinite combined carbon total.')
    return {'units': 'kgCO2e', 'buildings': len(identified), 'breakdown': totals,
            'total_embodied': totals['component_embodied_emissions'],
            'total_end_of_life': totals['component_end_of_life_emissions'],
            'total_reported_lca_scope': combined,
            'scope': 'Reported opening/envelope embodied and end-of-life emissions only.',
            'aggregation': 'component is opening + envelope; do not add constituents again.'}


def reconcile_outcome(payload, submitted_ids):
    """Account for calculated buildings and documented reader exclusions."""
    require(isinstance(payload, dict) and type(payload.get('schema_version')) is int
            and payload['schema_version'] == 1, 'LCA requires the versioned reader-outcome response.')
    require(isinstance(payload.get('results'), list) and isinstance(payload.get('exclusions'), list),
            'LCA outcome requires results and exclusions arrays.')
    report, identified = reconcile_results(payload['results'], submitted_ids)
    excluded = {}
    for index, exclusion in enumerate(payload['exclusions']):
        if not isinstance(exclusion, dict) or type(exclusion.get('feature_id')) is not int:
            report['issues'].append({'exclusion_index': index, 'reason': 'Missing or invalid exclusion feature_id.'})
            continue
        identifier = exclusion['feature_id']
        if identifier in excluded:
            report['issues'].append({'feature_id': identifier, 'reason': 'Duplicate exclusion ID.'})
        excluded[identifier] = exclusion
        if identifier in identified:
            report['issues'].append({'feature_id': identifier, 'reason': 'ID both calculated and excluded.'})
        area = exclusion.get('reader_floor_area_m2')
        minimum = exclusion.get('minimum_floor_area_m2')
        if (exclusion.get('reason_code') != 'reader_floor_area_below_minimum'
                or exclusion.get('field') != 'geometry'
                or not isinstance(exclusion.get('reason'), str) or not exclusion['reason'].strip()
                or type(area) not in (int, float) or not math.isfinite(area) or not 0 <= area < 25
                or type(minimum) not in (int, float) or minimum != 25):
            report['issues'].append({'feature_id': identifier, 'reason': 'Unsupported or invalid reader exclusion evidence.'})
    accounted = identified.keys() | excluded.keys()
    report['missing_ids'] = sorted(set(submitted_ids) - accounted)
    report['unexpected_ids'] = sorted(accounted - set(submitted_ids))
    report.update(calculated=len(payload['results']), excluded=len(payload['exclusions']),
                  accounted=len(accounted & set(submitted_ids)))
    expected = {'submitted': len(submitted_ids), 'calculated': report['calculated'], 'excluded': report['excluded']}
    counts = payload.get('counts')
    if (not isinstance(counts, dict) or set(counts) != set(expected)
            or any(type(counts[k]) is not int or counts[k] != value for k, value in expected.items())):
        report['issues'].append({'reason': 'LCA reported counts do not reconcile.'})
    report['status'] = 'failed' if report['issues'] or report['missing_ids'] or report['unexpected_ids'] else 'succeeded'
    report['identity_basis'] = 'feature_id partitions submitted records into calculated results and evidenced reader exclusions'
    return report, identified
