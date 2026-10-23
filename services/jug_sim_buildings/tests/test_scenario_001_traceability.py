"""
Sabu project
jug_sim_buildings package
test_scenario_001_traceability module
Verify H3B histories across duplicate selection and preparation exclusions.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from jug_sim_buildings.scenario_001.config import ScenarioConfig
from jug_sim_buildings.scenario_001.preparation import prepare_run
from jug_sim_buildings.scenario_001.traceability import write_trace, json_lines
from test_scenario_001_preparation import saved_run, feature, ControlledReprojector
from test_scenario_001_lca_results import result


class TestTraceability(unittest.TestCase):
    def test_rejected_features_and_identified_results_keep_original_references(self):
        with TemporaryDirectory() as root:
            bad = feature(11)
            bad['properties']['height'] = None
            store = saved_run(root, [feature(), bad])
            config = ScenarioConfig('http://cities', 'http://validation', root, fsa='H3B')
            preparation = prepare_run(store.directory, config, reprojector=ControlledReprojector())
            store.write_json('requests/lca.json', {'submitted_ids': [10]})
            store.write_json('lca/results.json', [result(10)])
            summary = write_trace(store, {'preparation': preparation, 'lca': {'status': 'succeeded'}})
            self.assertEqual(summary['identified_results'], 1)
            rows = json_lines(store.path('trace/records.jsonl'))
            self.assertEqual(rows[0]['lca']['submitted_id'], 10)
            self.assertEqual(rows[0]['source']['feature_id'], 10)
            self.assertEqual(rows[1]['preparation']['status'], 'rejected')
            self.assertIsNone(rows[1]['lca'])
            self.assertTrue(rows[1]['preparation']['errors'])

    def test_early_failure_creates_explicit_partial_history(self):
        with TemporaryDirectory() as root:
            store = saved_run(root)
            summary = write_trace(store, {'status': 'failed'})
            self.assertEqual(summary['status'], 'partial')
            self.assertEqual(summary['submitted_records'], 0)
