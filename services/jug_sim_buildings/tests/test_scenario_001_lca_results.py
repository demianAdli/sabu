"""
Sabu project
jug_sim_buildings package
test_scenario_001_lca_results module
Check identified results, reconciliation and carbon aggregation.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
import unittest

from jug_sim_buildings.scenario_001.lca_results import reconcile_results, carbon_summary


def result(identifier):
    return {'feature_id': identifier, 'opening_embodied_emissions': 1.,
            'envelope_embodied_emissions': 2., 'component_embodied_emissions': 3.,
            'opening_end_of_life_emissions': 4., 'envelope_end_of_life_emissions': 5.,
            'component_end_of_life_emissions': 9.}


class TestLCAResults(unittest.TestCase):
    def test_shuffled_identified_results_and_no_double_counting(self):
        report, mapped = reconcile_results([result(8), result(3)], [3, 8])
        self.assertEqual(report['status'], 'succeeded')
        self.assertEqual(mapped[3]['result_index'], 1)
        totals = carbon_summary(mapped)
        self.assertEqual(totals['total_reported_lca_scope'], 24.)
        self.assertEqual(totals['units'], 'kgCO2e')

    def test_missing_duplicate_unknown_and_identifierless_results_fail(self):
        for payload in ([result(1)], [result(1), result(1)], [result(1), result(9)],
                        [{k: v for k, v in result(1).items() if k != 'feature_id'}, result(2)],
                        [result(True), result(2)]):
            with self.subTest(payload=payload):
                self.assertEqual(reconcile_results(payload, [1, 2])[0]['status'], 'failed')

    def test_invalid_metric_and_subtotal_fail(self):
        for key, value in [('opening_embodied_emissions', None), ('component_embodied_emissions', 4),
                           ('opening_embodied_emissions', float('nan')),
                           ('opening_embodied_emissions', True)]:
            payload = deepcopy(result(1))
            payload[key] = value
            self.assertEqual(reconcile_results([payload], [1])[0]['status'], 'failed')
