"""Standalone application and shared fixtures for transport equivalence tests."""
import copy
from contextlib import contextmanager, ExitStack
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = REPO_ROOT / 'services' / 'jug_gis_validation'
for path in (SERVICE_ROOT, SERVICE_ROOT / 'src', REPO_ROOT / 'libs' / 'sabu_chassis' / 'src'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

SKIP_REASON = None
try:
    import geopandas as gpd
    import pandas as pd
    from jug_gis_validation.application.uniquification import GISUniquificationApplicationService
    from jug_gis_validation.domain_validation.uniquify_features import uniquify_features
    from jug_gis_validation.errors import GISValidationInputError
except ModuleNotFoundError as exc:
    if exc.name not in {'geopandas', 'pandas', 'matplotlib', 'numpy'}:
        raise
    SKIP_REASON = f'Service test dependency is not installed: {exc.name}'


def buildings_payload():
    # No census, function, floor, height, or postal-code properties. Duplicate
    # GeoJSON IDs deliberately cannot serve as record identities.
    rows = [
        {'roll_id': 'A', 'rank_area': 10, 'marker': 'a-small'},
        {'roll_id': None, 'rank_area': None, 'marker': 'missing'},
        {'roll_id': 'A', 'rank_area': '20', 'marker': 'a-large'},
        {'roll_id': 'B', 'rank_area': 5, 'marker': 'b-first'},
        {'roll_id': '   ', 'rank_area': 'unknown', 'marker': 'blank'},
        {'roll_id': 'B', 'rank_area': 5, 'marker': 'b-tied'},
        {'roll_id': 'C', 'rank_area': 'unknown', 'marker': 'singleton'},
    ]
    return {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'id': 'duplicated-id', 'properties': row,
         'geometry': {'type': 'Point', 'coordinates': [-73.5 + index * .001, 45.5]}}
        for index, row in enumerate(rows)
    ]}


@contextmanager
def no_validation_processing():
    """Any accidental validation, census, comparison, or plot work must fail."""
    targets = [
        'jug_gis_validation.application.jug_gis_validation.GISValidationApplicationService.run_validation',
        'jug_gis_validation.domain_validation.validate_gisoo.ValidateGISOO.__init__',
        'jug_gis_validation.domain_validation.validate_gisoo.ValidateGISOO._load_census_data_csv',
        'jug_gis_validation.domain_validation.validate_gisoo.ValidateGISOO.comparison_table',
        'jug_gis_validation.domain_validation.validate_gisoo.ValidateGISOO.plot_area_comparison',
        'jug_gis_validation.domain_validation.validate_gisoo.QueryCensusDataCSV',
        'pandas.read_csv',
        'matplotlib.pyplot.subplots',
    ]
    with ExitStack() as stack:
        mocks = [stack.enter_context(patch(target, side_effect=AssertionError(target)))
                 for target in targets]
        yield
        for mock in mocks:
            mock.assert_not_called()


def run_standalone(buildings):
    return GISUniquificationApplicationService.run_uniquification(
        buildings, unique_attribute_key='roll_id', area_key='rank_area')


@unittest.skipIf(SKIP_REASON, SKIP_REASON)
class TestUniquificationApplication(unittest.TestCase):
    def test_trace_reconciles_counts_and_maps_every_removed_record(self):
        payload = buildings_payload()
        original = copy.deepcopy(payload)
        with no_validation_processing():
            result = run_standalone(payload)
            body = result.as_dict()
        self.assertEqual(payload, original)
        stats = body['uniquification']
        self.assertEqual((stats['input_features'], stats['retained_features'],
                          stats['removed_features'], stats['duplicate_groups']), (7, 5, 2, 2))
        records = body['records']
        self.assertEqual(len(records), stats['input_features'])
        self.assertEqual(len({r['record_ref'] for r in records}), len(records))
        self.assertEqual([r['input_position'] for r in records], list(range(7)))
        retained = [r for r in records if r['status'] == 'retained']
        removed = [r for r in records if r['status'] == 'removed']
        self.assertEqual(len(retained), stats['retained_features'])
        self.assertEqual(len(removed), stats['removed_features'])
        self.assertEqual(stats['input_features'], len(retained) + len(removed))
        self.assertEqual(len(body['retained_geojson']['features']), len(retained))
        self.assertEqual([r['reason'] for r in records], [
            'smaller_area', 'missing_identifier', 'largest_area',
            'earliest_maximum_area', 'missing_identifier', 'later_tied_maximum',
            'unique_identifier'])
        by_ref = {r['record_ref']: r for r in retained}
        for record in records:
            winner = by_ref[record['retained_record_ref']]
            self.assertEqual(record['retained_feature_index'], winner['retained_feature_index'])
            feature = body['retained_geojson']['features'][record['retained_feature_index']]
            source = payload['features'][winner['input_position']]
            self.assertEqual(feature['geometry'], source['geometry'])
            self.assertEqual(feature['properties'], source['properties'])
        self.assertEqual(records[0]['retained_record_ref'], 'record:2')
        self.assertEqual(records[5]['retained_record_ref'], 'record:3')
        json.dumps(body, allow_nan=False)

    def test_duplicate_dataframe_indexes_and_nonfinite_singleton_areas(self):
        frame = gpd.GeoDataFrame.from_features(buildings_payload()['features'])
        frame.index = [3] * len(frame)
        frame.loc[:, 'rank_area'] = [10, float('inf'), 20, 5, float('nan'), 5, pd.NA]
        original = frame.copy(deep=True)
        expected, stats = uniquify_features(frame, unique_attribute_key='roll_id', area_key='rank_area')
        result = run_standalone(frame)
        pd.testing.assert_frame_equal(result.retained_features, expected)
        pd.testing.assert_frame_equal(frame, original)
        self.assertEqual(result.uniquification_stats, stats)
        body = result.as_dict()
        json.dumps(body, allow_nan=False)
        self.assertIsNone(body['records'][1]['area'])
        self.assertEqual(len({r['record_ref'] for r in body['records']}), len(frame))

    def test_extracted_loader_preserves_supported_inputs(self):
        payload = buildings_payload()
        expected = run_standalone(payload).as_dict()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.geojson'
            path.write_text(json.dumps(payload), encoding='utf-8')
            before = path.read_bytes()
            for source in (payload['features'], json.dumps(payload),
                           io.StringIO(json.dumps(payload)),
                           io.BytesIO(json.dumps(payload).encode()), path):
                with self.subTest(source_type=type(source).__name__):
                    self.assertEqual(run_standalone(source).as_dict(), expected)
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_configuration_is_actionable(self):
        for key in (None, '', '  ', 123):
            with self.subTest(key=key), self.assertRaisesRegex(
                    GISValidationInputError, 'unique_attribute_key'):
                GISUniquificationApplicationService.run_uniquification(
                    buildings_payload(), unique_attribute_key=key)


if __name__ == '__main__':
    unittest.main()
