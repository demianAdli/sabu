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
