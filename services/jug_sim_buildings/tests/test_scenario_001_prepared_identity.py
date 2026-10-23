"""
Sabu project
jug_sim_buildings package
test_scenario_001_prepared_identity module
Verify stable numeric IDs and complete positional provenance.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
import unittest

from jug_sim_buildings.scenario_001.prepared_identity import assign_identities, MAX_ID


class TestPreparedIdentity(unittest.TestCase):
    def test_missing_duplicate_and_invalid_ids_keep_distinct_provenance(self):
        candidates = [7, 7, 1, None, '001', True, -1, MAX_ID + 1, 0]
        features = [{'type': 'Feature', 'properties': {}, 'geometry': None} for _ in candidates]
        sources = [{'feature_id': v, 'feature_id_present': v is not None,
                    'record_ref': f'record:{i}', 'input_position': i}
                   for i, v in enumerate(candidates)]
        records = [{'record_ref': f'record:{i}', 'input_position': i, 'status': 'retained',
                    'retained_feature_index': i} for i in range(len(features))]
        records.append({'record_ref': 'record:9', 'input_position': 9,
                        'status': 'removed', 'retained_feature_index': 0})
        sources.append({'feature_id': 7, 'record_ref': 'record:9', 'input_position': 9})
        original = deepcopy(features)
        prepared, mappings = assign_identities(features, records, sources, fsa='H3B', run_id='run')
        ids = [f['id'] for f in prepared]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids[2], 1)
        self.assertEqual(ids[-1], 0)
        self.assertEqual([m['id_action'] for m in mappings[:2]], ['assigned', 'assigned'])
        self.assertEqual(len(mappings[0]['input_records']), 2)
        self.assertEqual(prepared[0]['properties']['name'], f'H3B_{ids[0]}')
        self.assertEqual(features, original)
        self.assertEqual(assign_identities(features, records, sources, fsa='H3B', run_id='run'),
                         (prepared, mappings))
