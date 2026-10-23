"""
Sabu project
jug_sim_buildings package
prepared_identity module
Assign stable prepared identities and consolidate source references.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from collections import Counter, defaultdict
from copy import deepcopy


MAX_ID = 2**53 - 1


def assign_identities(features, records, sources, *, fsa, run_id):
    winners = {r['retained_feature_index']: r for r in records if r['status'] == 'retained'}
    inputs = defaultdict(list)
    for record in records:
        inputs[record['retained_feature_index']].append(record)
    candidates = [feature.get('id', sources[winners[i]['input_position']].get('feature_id'))
                  for i, feature in enumerate(features)]
    counts = Counter(v for v in candidates if type(v) is int and 0 <= v <= MAX_ID)
    reserved = {v for v, count in counts.items() if count == 1}
    next_id = 1
    prepared, mappings = [], []
    for index, feature in enumerate(features):
        candidate = candidates[index]
        preserved = type(candidate) is int and counts.get(candidate) == 1 and 0 <= candidate <= MAX_ID
        if preserved:
            prepared_id = candidate
        else:
            while next_id in reserved:
                next_id += 1
            if next_id > MAX_ID:
                raise ValueError('Prepared ID range exhausted.')
            prepared_id = next_id
            reserved.add(prepared_id)
            next_id += 1
        output = deepcopy(feature)
        output['id'] = prepared_id
        value = output['properties'].get('name')
        generated = value is None or isinstance(value, str) and not value.strip()
        if generated:
            output['properties']['name'] = f'{fsa}_{prepared_id}'
        prepared.append(output)
        mappings.append({
            'run_id': run_id, 'fsa': fsa, 'retained_feature_index': index,
            'prepared_id': prepared_id, 'source_id_candidate': candidate,
            'id_action': 'preserved' if preserved else 'assigned',
            'name_generated': generated, 'original_name': feature['properties'].get('name'),
            'winner_record_ref': winners[index]['record_ref'],
            'input_records': [
                {'record_ref': r['record_ref'], 'input_position': r['input_position'],
                 'uniquification_status': r['status'],
                 'source': deepcopy(sources[r['input_position']])}
                for r in inputs[index]],
        })
    return prepared, mappings
