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

from jug_sim_buildings.scenario_001.lca_results import reconcile_results, reconcile_outcome, carbon_summary


def result(identifier):
    return {'feature_id': identifier, 'opening_embodied_emissions': 1.,
            'envelope_embodied_emissions': 2., 'component_embodied_emissions': 3.,
            'opening_end_of_life_emissions': 4., 'envelope_end_of_life_emissions': 5.,
            'component_end_of_life_emissions': 9.}


def exclusion(identifier, area=10.):
    return {'feature_id': identifier, 'reason_code': 'reader_floor_area_below_minimum',
            'field': 'geometry', 'reason': 'Reader floor area below existing minimum.',
            'reader_floor_area_m2': area, 'minimum_floor_area_m2': 25.}


def outcome(results, exclusions=None):
    exclusions = exclusions or []
    return {'schema_version': 1, 'results': results, 'exclusions': exclusions,
            'counts': {'submitted': len(results) + len(exclusions), 'calculated': len(results), 'excluded': len(exclusions)}}


class TestLCAResults(unittest.TestCase):
    def test_results_and_evidenced_exclusions_partition_submissions(self):
        report, mapped = reconcile_outcome(outcome([result(8)], [exclusion(3)]), [3, 8])
        self.assertEqual(report['status'], 'succeeded')
        self.assertEqual((report['calculated'], report['excluded'], report['accounted']), (1, 1, 2))
        self.assertEqual(carbon_summary(mapped)['total_reported_lca_scope'], 12.)

    def test_bad_exclusions_overlap_counts_and_unexplained_omissions_fail(self):
        values = [outcome([result(1)], [exclusion(1)]),
                  outcome([result(1)], [exclusion(2), exclusion(2)]),
                  outcome([result(1)], [exclusion(9)]),
                  outcome([result(1)]), outcome([result(1)], [exclusion(2, 25)]),
                  outcome([result(1)], [{**exclusion(2), 'reason_code': 'unknown'}]),
                  outcome([result(1)], [{**exclusion(2), 'reader_floor_area_m2': True}]),
                  {**outcome([result(1)], [exclusion(2)]), 'counts': {'submitted': 2, 'calculated': 2, 'excluded': 0}}]
        for payload in values:
            with self.subTest(payload=payload):
                self.assertEqual(reconcile_outcome(payload, [1, 2])[0]['status'], 'failed')

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
