import os
import sys
import unittest
from unittest.mock import patch


_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_SERVICE_SRC = os.path.join(
    _REPO_ROOT, 'services', 'jug_gis_validation', 'src')
_SABU_CHASSIS_SRC = os.path.join(_REPO_ROOT, 'libs', 'sabu_chassis', 'src')
for path in (_SERVICE_SRC, _SABU_CHASSIS_SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

_DEPS_SKIP_REASON = None
try:
    import geopandas as gpd
    import pandas as pd
    from jug_gis_validation import __main__ as validation_cli
    from jug_gis_validation.application import (
        AreaCalculationMode,
        GISValidationApplicationService,
        GISValidationOutputMode,
        GISValidationPlotMetric,
    )
    from jug_gis_validation.domain_validation.validate_gisoo import ValidateGISOO
    from jug_gis_validation.errors import (
        GISValidationCalculationError,
        GISValidationDataContractError,
        GISValidationInputError,
    )
except ModuleNotFoundError as exc:
    if exc.name in {'pandas', 'geopandas', 'matplotlib', 'numpy'}:
        _DEPS_SKIP_REASON = (
            f'jug_gis_validation test dependency is not installed: {exc.name}'
        )
        pd = None
        gpd = None
        ValidateGISOO = None
        GISValidationCalculationError = None
        GISValidationDataContractError = None
        GISValidationInputError = None
        GISValidationApplicationService = None
        GISValidationOutputMode = None
        GISValidationPlotMetric = None
        AreaCalculationMode = None
        validation_cli = None
    else:
        raise


def _buildings_feature_collection(postal_code='H2X 1A1'):
    return {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {
                    'postal': postal_code,
                    'function': 'residential',
                    'area': 100,
                    'floors': 2,
                    'height': 7,
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-73.56, 45.51],
                },
            },
        ],
    }


def _census_dataframe(code='H2X', single_detached_count=2):
    return pd.DataFrame(
        [
            {
                'CODE': code,
                'CHARACTERISTIC_NAME': 'Total private dwellings',
                'COUNT': 10,
            },
            {
                'CODE': code,
                'CHARACTERISTIC_NAME': (
                    'Total - Private households by household size - 100% data'
                ),
                'COUNT': 8,
            },
            {
                'CODE': code,
                'CHARACTERISTIC_NAME': 'Single-detached house',
                'COUNT': single_detached_count,
            },
        ]
    )


def _default_buildings_feature_collection(postal_code='H2X 1A1'):
    return {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {
                    'fsa': postal_code,
                    'function': '1000',
                    'area': 100,
                    'floor_num': 2,
                    'height': 7,
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-73.56, 45.51],
                },
            },
        ],
    }


def _duplicate_buildings_feature_collection():
    buildings = _default_buildings_feature_collection()
    first = buildings['features'][0]
    first['properties']['roll_provincial_id'] = 'ROLL-A'
    first['properties']['citygisoo_area'] = 300
    first['properties']['roll_area'] = 10
    first['properties']['main_floor_area'] = None
    second = {
        'type': 'Feature',
        'properties': dict(first['properties']),
        'geometry': {
            'type': 'Point',
            'coordinates': [-73.57, 45.52],
        },
    }
    second['properties']['area'] = 200
    second['properties']['citygisoo_area'] = 200
    second['properties']['roll_area'] = 1000
    second['properties']['main_floor_area'] = 200
    missing_id = {
        'type': 'Feature',
        'properties': dict(first['properties']),
        'geometry': {
            'type': 'Point',
            'coordinates': [-73.58, 45.53],
        },
    }
    missing_id['properties']['roll_provincial_id'] = None
    missing_id['properties']['area'] = 50
    missing_id['properties']['citygisoo_area'] = 50
    missing_id['properties']['roll_area'] = 20
    missing_id['properties']['main_floor_area'] = 40
    buildings['features'].extend([second, missing_id])
    return buildings


def _default_census_dataframe(code='H2X'):
    return pd.DataFrame(
        [
            {
                'ALT_GEO_CODE': code,
                'CHARACTERISTIC_NAME': 'Total private dwellings',
                'C1_COUNT_TOTAL': 10,
            },
            {
                'ALT_GEO_CODE': code,
                'CHARACTERISTIC_NAME': (
                    'Total - Private households by household size - 100% data'
                ),
                'C1_COUNT_TOTAL': 8,
            },
            {
                'ALT_GEO_CODE': code,
                'CHARACTERISTIC_NAME': 'Single-detached house',
                'C1_COUNT_TOTAL': 2,
            },
        ]
    )


def _unit_count_buildings(unit_values):
    buildings = _default_buildings_feature_collection()
    template = buildings['features'][0]
    features = []
    for index, unit_value in enumerate(unit_values):
        feature = {
            'type': 'Feature',
            'properties': dict(template['properties']),
            'geometry': {
                'type': 'Point',
                'coordinates': [-73.56 - index * 0.001, 45.51],
            },
        }
        feature['properties']['unit_num'] = unit_value
        features.append(feature)
    buildings['features'] = features
    return buildings


@unittest.skipIf(_DEPS_SKIP_REASON is not None, _DEPS_SKIP_REASON)
class TestValidateGISOOInputs(unittest.TestCase):
    def test_loading_helpers_remain_compatible_after_extraction(self):
        import json
        from jug_gis_validation.domain_validation.buildings_input import load_buildings_set
        payload = _default_buildings_feature_collection()
        expected, source = load_buildings_set(payload)
        frame, legacy_source = ValidateGISOO._load_buildings_set(payload)
        pd.testing.assert_frame_equal(frame, expected)
        self.assertEqual(source, legacy_source)
        pd.testing.assert_frame_equal(
            ValidateGISOO._geojson_to_geodataframe(payload), expected)
        pd.testing.assert_frame_equal(
            ValidateGISOO._geojson_text_to_geodataframe(json.dumps(payload)), expected)

    def test_legacy_cli_still_dispatches_validation(self):
        with patch.object(validation_cli, 'configure_service_logging'), \
                patch.object(GISValidationApplicationService, 'run_validation',
                             side_effect=RuntimeError('validation called')) as run:
            self.assertEqual(validation_cli.main(['--buildings-set', 'input.geojson']), 1)
        run.assert_called_once()

    def test_cli_accepts_unique_attribute_key(self):
        args = validation_cli._build_parser().parse_args([
            '--buildings-set',
            'buildings.geojson',
            '--unique-attribute-key',
            'roll_provincial_id',
            '--uniquification-area-key',
            'citygisoo_area',
            '--area-calculation-mode',
            'area-only',
            '--cleaned-units-num-key',
            'unit_num',
            '--include-height-proxy',
            '--height-proxy-area-key',
            'citygisoo_area',
            '--height-proxy-area-fallback-key',
            'roll_area',
            '--uniquified-output-path',
            'uniquified.geojson',
        ])

        self.assertEqual(args.unique_attribute_key, 'roll_provincial_id')
        self.assertEqual(args.uniquification_area_key, 'citygisoo_area')
        self.assertEqual(args.area_calculation_mode, 'area-only')
        self.assertEqual(args.cleaned_units_num_key, 'unit_num')
        self.assertTrue(args.include_height_proxy)
        self.assertEqual(args.height_proxy_area_key, 'citygisoo_area')
        self.assertEqual(args.height_proxy_area_fallback_key, 'roll_area')
        self.assertIsNone(args.height_proxy_area_fallback_value)
        self.assertEqual(args.uniquified_output_path, 'uniquified.geojson')

    def test_geojson_dict_and_custom_census_dataframe(self):
        validator = ValidateGISOO(
            _buildings_feature_collection(),
            'CODE',
            'COUNT',
            'postal',
            'function',
            'residential',
            'area',
            'floors',
            census_data_csv=_census_dataframe(),
        )

        self.assertEqual(validator.district_codes, ('H2X',))
        self.assertEqual(
            validator.clean_district_and_census_unit('H2X'),
            (1, 8.0))

    def test_default_packaged_census_is_used_when_not_provided(self):
        validator = ValidateGISOO(
            _buildings_feature_collection(),
            'ALT_GEO_CODE',
            'C1_COUNT_TOTAL',
            'postal',
            'function',
            'residential',
            'area',
            'floors',
        )

        self.assertEqual(validator._census_source, 'packaged:filtered_census.csv')

    def test_missing_buildings_column_raises_contract_error(self):
        buildings = _buildings_feature_collection()
        del buildings['features'][0]['properties']['floors']

        with self.assertRaises(GISValidationDataContractError):
            ValidateGISOO(
                buildings,
                'CODE',
                'COUNT',
                'postal',
                'function',
                'residential',
                'area',
                'floors',
                census_data_csv=_census_dataframe(),
            )

    def test_zero_census_area_raises_clear_calculation_error(self):
        validator = ValidateGISOO(
            _buildings_feature_collection(),
            'CODE',
            'COUNT',
            'postal',
            'function',
            'residential',
            'area',
            'floors',
            census_data_csv=_census_dataframe(single_detached_count=0),
        )

        with self.assertRaises(GISValidationCalculationError):
            validator.clean_district_vs_census_area('H2X')

    def test_application_run_validation_uses_default_field_names(self):
        output_lines = []

        result = GISValidationApplicationService.run_validation(
            _default_buildings_feature_collection(),
            census_data_csv=_default_census_dataframe(),
            output_mode=GISValidationOutputMode.CONSOLE,
            console_writer=output_lines.append,
        )

        self.assertEqual(result.codes, ('H2X',))
        self.assertIsNone(result.csv_path)
        self.assertIsNone(result.plot_path)
        self.assertEqual(len(output_lines), 1)
        self.assertIn('FSA', output_lines[0])
        self.assertFalse(result.uniquification_stats.applied)
        self.assertEqual(result.uniquification_stats.input_features, 1)
        self.assertEqual(
            result.area_calculation_mode,
            AreaCalculationMode.AREA_TIMES_FLOOR)
        self.assertFalse(result.height_proxy_included)
        self.assertEqual(
            result.comparison_table['Cleaned Total Area'],
            [200.0])
        self.assertNotIn(
            'Cleaned Total Area (height proxy)',
            result.comparison_table)

    def test_cleaned_units_can_sum_configured_feature_field(self):
        buildings = _unit_count_buildings([1, 1, 1, 1, 1, 2, 2, 2, 3, 3])

        result = GISValidationApplicationService.run_validation(
            buildings,
            census_data_csv=_default_census_dataframe(),
            cleaned_units_num_key='unit_num',
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(result.comparison_table['Cleaned Units Num'], [17])

    def test_cleaned_units_null_defaults_to_one(self):
        result = GISValidationApplicationService.run_validation(
            _unit_count_buildings([None, 2]),
            census_data_csv=_default_census_dataframe(),
            cleaned_units_num_key='unit_num',
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(result.comparison_table['Cleaned Units Num'], [3])

    def test_cleaned_units_legacy_mode_still_counts_features(self):
        buildings = _unit_count_buildings([5] * 10)

        result = GISValidationApplicationService.run_validation(
            buildings,
            census_data_csv=_default_census_dataframe(),
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(result.comparison_table['Cleaned Units Num'], [10])

    def test_cleaned_units_keep_existing_function_filter(self):
        buildings = _unit_count_buildings([1, 2])
        buildings['features'][1]['properties']['function'] = '2000'
        buildings['features'][1]['properties']['unit_num'] = 100

        result = GISValidationApplicationService.run_validation(
            buildings,
            census_data_csv=_default_census_dataframe(),
            cleaned_units_num_key='unit_num',
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(result.comparison_table['Cleaned Units Num'], [1])

    def test_invalid_cleaned_unit_value_raises_contract_error(self):
        with self.assertRaisesRegex(
                GISValidationDataContractError,
                'finite, non-negative integers'):
            GISValidationApplicationService.run_validation(
                _unit_count_buildings([1.5]),
                census_data_csv=_default_census_dataframe(),
                cleaned_units_num_key='unit_num',
                output_mode=GISValidationOutputMode.NONE,
            )

    def test_missing_cleaned_unit_field_raises_contract_error(self):
        with self.assertRaisesRegex(
                GISValidationDataContractError,
                'unit_num'):
            GISValidationApplicationService.run_validation(
                _default_buildings_feature_collection(),
                census_data_csv=_default_census_dataframe(),
                cleaned_units_num_key='unit_num',
                output_mode=GISValidationOutputMode.NONE,
            )

    def test_no_area_mode_does_not_require_area_floor_or_height(self):
        buildings = _unit_count_buildings([3])
        properties = buildings['features'][0]['properties']
        del properties['area']
        del properties['floor_num']
        del properties['height']

        result = GISValidationApplicationService.run_validation(
            buildings,
            census_data_csv=_default_census_dataframe(),
            cleaned_units_num_key='unit_num',
            area_calculation_mode=AreaCalculationMode.NONE,
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(result.comparison_table['Cleaned Units Num'], [3])
        self.assertNotIn('Cleaned Total Area', result.comparison_table)
        self.assertNotIn(
            'Census Total Area (by type)',
            result.comparison_table)
        self.assertIsNone(result.validator._census_data.total_area)

    def test_no_area_mode_rejects_height_proxy(self):
        with self.assertRaisesRegex(ValueError, 'cannot be enabled'):
            GISValidationApplicationService.run_validation(
                _default_buildings_feature_collection(),
                census_data_csv=_default_census_dataframe(),
                area_calculation_mode=AreaCalculationMode.NONE,
                include_height_proxy=True,
                output_mode=GISValidationOutputMode.NONE,
            )

    def test_cleaned_units_are_summed_after_uniquification(self):
        buildings = _duplicate_buildings_feature_collection()
        buildings['features'][0]['properties']['unit_num'] = 4
        buildings['features'][1]['properties']['unit_num'] = 50
        buildings['features'][2]['properties']['unit_num'] = None

        result = GISValidationApplicationService.run_validation(
            buildings,
            census_data_csv=_default_census_dataframe(),
            cleaned_units_num_key='unit_num',
            unique_attribute_key='roll_provincial_id',
            uniquification_area_key='citygisoo_area',
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(result.comparison_table['Cleaned Units Num'], [5])

    def test_area_only_does_not_require_floor_or_height(self):
        buildings = _default_buildings_feature_collection()
        properties = buildings['features'][0]['properties']
        del properties['floor_num']
        del properties['height']

        result = GISValidationApplicationService.run_validation(
            buildings,
            census_data_csv=_default_census_dataframe(),
            area_calculation_mode=AreaCalculationMode.AREA_ONLY,
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(
            result.comparison_table['Cleaned Total Area'],
            [100.0])
        self.assertFalse(result.height_proxy_included)

    def test_height_proxy_is_opt_in_and_clearly_labeled(self):
        result = GISValidationApplicationService.run_validation(
            _default_buildings_feature_collection(),
            census_data_csv=_default_census_dataframe(),
            include_height_proxy=True,
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertTrue(result.height_proxy_included)
        self.assertEqual(
            result.comparison_table['Cleaned Total Area (height proxy)'],
            [200.0])

    def test_height_proxy_can_use_a_different_area_field(self):
        result = GISValidationApplicationService.run_validation(
            _duplicate_buildings_feature_collection(),
            census_data_csv=_default_census_dataframe(),
            area_key='roll_area',
            area_calculation_mode=AreaCalculationMode.AREA_ONLY,
            unique_attribute_key='roll_provincial_id',
            uniquification_area_key='citygisoo_area',
            include_height_proxy=True,
            height_proxy_area_key='citygisoo_area',
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(
            result.comparison_table['Cleaned Total Area'],
            [30.0])
        self.assertEqual(
            result.comparison_table['Cleaned Total Area (height proxy)'],
            [700.0])
        self.assertEqual(result.height_proxy_area_key, 'citygisoo_area')

    def test_height_proxy_area_can_fall_back_to_another_field(self):
        buildings = _duplicate_buildings_feature_collection()

        result = GISValidationApplicationService.run_validation(
            buildings,
            census_data_csv=_default_census_dataframe(),
            unique_attribute_key='roll_provincial_id',
            uniquification_area_key='citygisoo_area',
            include_height_proxy=True,
            height_proxy_area_key='main_floor_area',
            height_proxy_area_fallback_key='citygisoo_area',
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(
            result.comparison_table['Cleaned Total Area (height proxy)'],
            [680.0])
        stats = result.height_proxy_area_resolution_stats
        self.assertEqual(stats.fallback_type, 'field')
        self.assertEqual(stats.fallback_key, 'citygisoo_area')
        self.assertEqual(stats.fallback_features, 1)
        self.assertEqual(stats.fallback_percentage, 50.0)
        self.assertIsNone(
            buildings['features'][0]['properties']['main_floor_area'])

    def test_height_proxy_area_uses_explicit_constant_fallback(self):
        result = GISValidationApplicationService.run_validation(
            _duplicate_buildings_feature_collection(),
            census_data_csv=_default_census_dataframe(),
            unique_attribute_key='roll_provincial_id',
            uniquification_area_key='citygisoo_area',
            include_height_proxy=True,
            height_proxy_area_key='main_floor_area',
            height_proxy_area_fallback_value=90,
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(
            result.comparison_table['Cleaned Total Area (height proxy)'],
            [260.0])
        stats = result.height_proxy_area_resolution_stats
        self.assertEqual(stats.fallback_type, 'constant')
        self.assertEqual(stats.fallback_value, 90.0)
        self.assertEqual(stats.fallback_features, 1)

    def test_height_proxy_area_constant_defaults_to_eighty(self):
        result = GISValidationApplicationService.run_validation(
            _duplicate_buildings_feature_collection(),
            census_data_csv=_default_census_dataframe(),
            unique_attribute_key='roll_provincial_id',
            uniquification_area_key='citygisoo_area',
            include_height_proxy=True,
            height_proxy_area_key='main_floor_area',
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(
            result.comparison_table['Cleaned Total Area (height proxy)'],
            [240.0])
        self.assertEqual(
            result.height_proxy_area_resolution_stats.fallback_value,
            80.0)

    def test_height_proxy_fallback_options_are_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError, 'mutually exclusive'):
            GISValidationApplicationService.run_validation(
                _default_buildings_feature_collection(),
                census_data_csv=_default_census_dataframe(),
                include_height_proxy=True,
                height_proxy_area_fallback_key='area',
                height_proxy_area_fallback_value=80,
                output_mode=GISValidationOutputMode.NONE,
            )

    def test_height_proxy_fallback_value_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, 'greater than zero'):
            GISValidationApplicationService.run_validation(
                _default_buildings_feature_collection(),
                census_data_csv=_default_census_dataframe(),
                include_height_proxy=True,
                height_proxy_area_fallback_value=0,
                output_mode=GISValidationOutputMode.NONE,
            )

    def test_unusable_fallback_field_value_raises_contract_error(self):
        buildings = _duplicate_buildings_feature_collection()
        buildings['features'][0]['properties']['roll_area'] = None

        with self.assertRaisesRegex(
                GISValidationDataContractError,
                'fallback field'):
            GISValidationApplicationService.run_validation(
                buildings,
                census_data_csv=_default_census_dataframe(),
                unique_attribute_key='roll_provincial_id',
                uniquification_area_key='citygisoo_area',
                include_height_proxy=True,
                height_proxy_area_key='main_floor_area',
                height_proxy_area_fallback_key='roll_area',
                output_mode=GISValidationOutputMode.NONE,
            )

    def test_application_exports_exact_uniquified_snapshot(self):
        import tempfile

        buildings = _duplicate_buildings_feature_collection()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'H2X_uniquified.geojson')

            result = GISValidationApplicationService.run_validation(
                buildings,
                census_data_csv=_default_census_dataframe(),
                unique_attribute_key='roll_provincial_id',
                uniquification_area_key='citygisoo_area',
                uniquified_output_path=output_path,
                output_mode=GISValidationOutputMode.NONE,
            )

            exported = gpd.read_file(output_path)
            self.assertEqual(len(exported), 2)
            self.assertEqual(set(exported['roll_area']), {10, 20})
            self.assertEqual(result.uniquified_output_path.name,
                             'H2X_uniquified.geojson')
            self.assertEqual(len(buildings['features']), 3)

    def test_uniquified_output_requires_uniquification(self):
        with self.assertRaises(GISValidationInputError):
            GISValidationApplicationService.run_validation(
                _default_buildings_feature_collection(),
                census_data_csv=_default_census_dataframe(),
                uniquified_output_path='unused.geojson',
                output_mode=GISValidationOutputMode.NONE,
            )

    def test_application_uniquifies_only_its_validation_snapshot(self):
        buildings = _duplicate_buildings_feature_collection()

        result = GISValidationApplicationService.run_validation(
            buildings,
            census_data_csv=_default_census_dataframe(),
            unique_attribute_key='roll_provincial_id',
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(len(buildings['features']), 3)
        self.assertTrue(result.uniquification_stats.applied)
        self.assertEqual(result.uniquification_stats.input_features, 3)
        self.assertEqual(result.uniquification_stats.retained_features, 2)
        self.assertEqual(result.uniquification_stats.removed_features, 1)
        self.assertEqual(result.uniquification_stats.duplicate_groups, 1)
        self.assertEqual(
            result.validator.clean_district_and_census_unit('H2X'),
            (2, 8.0))

    def test_application_can_rank_and_validate_with_different_area_fields(self):
        buildings = _duplicate_buildings_feature_collection()

        result = GISValidationApplicationService.run_validation(
            buildings,
            census_data_csv=_default_census_dataframe(),
            area_key='roll_area',
            unique_attribute_key='roll_provincial_id',
            uniquification_area_key='citygisoo_area',
            output_mode=GISValidationOutputMode.NONE,
        )

        self.assertEqual(
            result.uniquification_stats.ranking_area_key,
            'citygisoo_area')
        self.assertEqual(
            result.validator.district_codes_info['H2X'],
            (2, 60.0))

    def test_application_writes_csv_when_requested(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            result = GISValidationApplicationService.run_validation(
                _default_buildings_feature_collection(),
                census_data_csv=_default_census_dataframe(),
                output_mode=GISValidationOutputMode.CSV,
                district_name='test_district',
                output_dir=tmpdir,
            )

            self.assertIsNotNone(result.csv_path)
            self.assertTrue(result.csv_path.exists())
            self.assertEqual(
                result.csv_path.name,
                'validate_test_district_gisoo.csv')

    def test_application_writes_plot_when_requested(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            plot_path = os.path.join(tmpdir, 'comparison.png')
            result = GISValidationApplicationService.run_validation(
                _default_buildings_feature_collection(),
                census_data_csv=_default_census_dataframe(),
                output_mode=GISValidationOutputMode.NONE,
                include_plot=True,
                plot_path=plot_path,
            )

            self.assertEqual(str(result.plot_path), os.path.abspath(plot_path))
            self.assertTrue(result.plot_path.exists())

    def test_application_can_plot_unit_counts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            plot_path = os.path.join(tmpdir, 'unit_comparison.png')
            with patch.object(
                    ValidateGISOO,
                    'plot_area_comparison',
                    wraps=ValidateGISOO.plot_area_comparison) as plot_mock:
                result = GISValidationApplicationService.run_validation(
                    _default_buildings_feature_collection(),
                    census_data_csv=_default_census_dataframe(),
                    output_mode=GISValidationOutputMode.NONE,
                    include_plot=True,
                    plot_path=plot_path,
                    plot_metric=GISValidationPlotMetric.UNITS,
                    district_name='H2X',
                )

            plot_args = plot_mock.call_args.kwargs
            self.assertEqual(plot_args['areas'].name, 'Cleaned Units Num')
            self.assertEqual(plot_args['census_areas'].name, 'Census Units Num')
            self.assertEqual(plot_args['y_label'], 'Number of units')
            self.assertEqual(plot_args['title'], 'Unit comparison - H2X')
            self.assertTrue(result.plot_path.exists())


if __name__ == '__main__':
    unittest.main()
