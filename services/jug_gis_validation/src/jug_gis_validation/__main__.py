"""Direct Python execution entrypoint for jug_gis_validation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sabu_chassis.logging import get_logger

from .application import (
    GISUniquificationApplicationService,
    AreaCalculationMode,
    GISValidationApplicationService,
    GISValidationOutputMode,
    GISValidationPlotMetric,
)
from .application.jug_gis_validation import (
    DEFAULT_AREA_KEY,
    DEFAULT_CENSUS_CODE_FIELD_TITLE,
    DEFAULT_CENSUS_DATA_CSV,
    DEFAULT_CENSUS_UNITS_NUM_TITLE,
    DEFAULT_DISTRICT_NAME,
    DEFAULT_FLOOR_NUM_KEY,
    DEFAULT_FUNCTION_KEY,
    DEFAULT_FUNCTION_VALUE,
    DEFAULT_HEIGHT_KEY,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_POSTAL_CODE_KEY,
)
from .logging_setup import configure_service_logging


logger = get_logger(__name__)


def _build_parser():
    parser = argparse.ArgumentParser(
        description=(
            'Run a jug_gis_validation workflow directly. '
            'Use "uniquify --help" for standalone uniquification.'))
    parser.add_argument(
        '--buildings-set',
        required=True,
        help='Path to a buildings_set GeoJSON file.')
    parser.add_argument(
        '--census-data-csv',
        default=DEFAULT_CENSUS_DATA_CSV,
        help='Census CSV path or packaged default data/filtered_census.csv.')
    parser.add_argument(
        '--census-code-field-title',
        default=DEFAULT_CENSUS_CODE_FIELD_TITLE,
        help='Census field containing FSA/code values.')
    parser.add_argument(
        '--census-units-num-title',
        default=DEFAULT_CENSUS_UNITS_NUM_TITLE,
        help='Census field containing count values.')
    parser.add_argument(
        '--postal-code-key',
        default=DEFAULT_POSTAL_CODE_KEY,
        help='buildings_set field containing FSA/postal-code values.')
    parser.add_argument(
        '--function-key',
        default=DEFAULT_FUNCTION_KEY,
        help='buildings_set field containing building function values.')
    parser.add_argument(
        '--function-value',
        default=DEFAULT_FUNCTION_VALUE,
        help='Function value to keep during validation.')
    parser.add_argument(
        '--cleaned-units-num-key',
        help=(
            'Optional buildings_set field containing the number of units per '
            'feature. NULL values count as one; when omitted, every feature '
            'counts as one unit.'))
    parser.add_argument(
        '--area-key',
        default=DEFAULT_AREA_KEY,
        help='buildings_set field containing area values.')
    parser.add_argument(
        '--floor-num-key',
        default=DEFAULT_FLOOR_NUM_KEY,
        help='buildings_set field containing floor-number values.')
    parser.add_argument(
        '--area-calculation-mode',
        default=AreaCalculationMode.AREA_TIMES_FLOOR.value,
        choices=[mode.value for mode in AreaCalculationMode],
        help=(
            'How to calculate feature area: use area directly or multiply '
            'it by floor number (default: area-times-floor).'))
    parser.add_argument(
        '--height-key',
        default=DEFAULT_HEIGHT_KEY,
        help='buildings_set field containing height values for proxy output.')
    parser.add_argument(
        '--include-height-proxy',
        action='store_true',
        help='Include a separate height-derived area diagnostic.')
    parser.add_argument(
        '--height-proxy-area-key',
        help=(
            'Optional base-area field used only by the height proxy. '
            'Defaults to --area-key.'))
    height_proxy_fallback = parser.add_mutually_exclusive_group()
    height_proxy_fallback.add_argument(
        '--height-proxy-area-fallback-key',
        help='Optional field used when the height-proxy area is unusable.')
    height_proxy_fallback.add_argument(
        '--height-proxy-area-fallback-value',
        type=float,
        help=(
            'Positive constant used when the height-proxy area is unusable. '
            'Defaults to 80 when neither fallback option is supplied.'))
    parser.add_argument(
        '--unique-attribute-key',
        help=(
            'Optional buildings_set field to uniquify for validation. The '
            'feature with the greatest ranking-area value is retained.'))
    parser.add_argument(
        '--uniquification-area-key',
        help=(
            'Optional area field used only to rank duplicate features. '
            'Defaults to --area-key.'))
    parser.add_argument(
        '--uniquified-output-path',
        help=(
            'Optional .geojson/.json path for the feature snapshot retained '
            'by uniquification. Requires --unique-attribute-key.'))
    parser.add_argument(
        '--census-avg-area-json',
        help=(
            'Optional JSON object or path to a JSON file with average area '
            'values by census dwelling type.'))
    parser.add_argument(
        '--output-mode',
        default=GISValidationOutputMode.CONSOLE.value,
        choices=[mode.value for mode in GISValidationOutputMode],
        help='How to output the comparison table.')
    parser.add_argument(
        '--district-name',
        default=DEFAULT_DISTRICT_NAME,
        help='Name used for default CSV and plot filenames.')
    parser.add_argument(
        '--output-dir',
        default=DEFAULT_OUTPUT_DIR,
        help='Directory used for default CSV and plot outputs.')
    parser.add_argument(
        '--csv-path',
        help='Optional explicit CSV output path.')
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Save a comparison plot.')
    parser.add_argument(
        '--plot-metric',
        default=GISValidationPlotMetric.AREA.value,
        choices=[metric.value for metric in GISValidationPlotMetric],
        help='Metric to compare in the plot (default: area).')
    parser.add_argument(
        '--plot-path',
        help='Optional explicit plot output path.')
    parser.add_argument(
        '--plot-title',
        help='Optional plot title.')
    return parser


def _load_census_avg_area(raw_value):
    if not raw_value:
        return None

    candidate_path = Path(raw_value)
    if candidate_path.exists():
        raw_value = candidate_path.read_text(encoding='utf-8')

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            '--census-avg-area-json must be a JSON object or a JSON file path.'
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError('--census-avg-area-json must resolve to a JSON object.')
    return parsed


def _uniquify_main(argv):
    parser = argparse.ArgumentParser(
        prog='python -m jug_gis_validation uniquify',
        description='Uniquify features without census processing or comparisons.')
    parser.add_argument('--buildings-set', required=True,
                        help='Input GeoJSON file path.')
    parser.add_argument('--unique-attribute-key', required=True,
                        help='Property identifying duplicate groups.')
    parser.add_argument('--area-key', default='area',
                        help='Property used to rank duplicates (default: area).')
    parser.add_argument('--output-path',
                        help='Write the complete JSON result here instead of stdout.')
    args = parser.parse_args(argv)
    try:
        source_path = Path(args.buildings_set).expanduser().resolve()
        output_path = (
            Path(args.output_path).expanduser().resolve()
            if args.output_path else None)
        if output_path is not None and (
                source_path == output_path
                or (output_path.exists() and source_path.exists()
                    and source_path.samefile(output_path))):
            raise ValueError('--output-path must not overwrite the input file.')
        result = GISUniquificationApplicationService.run_uniquification(
            args.buildings_set,
            unique_attribute_key=args.unique_attribute_key,
            area_key=args.area_key)
        serialized = json.dumps(result.as_dict(), allow_nan=False, indent=2)
        if output_path is None:
            print(serialized)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(serialized + '\n', encoding='utf-8')
    except Exception as exc:
        print(f'Uniquification failed: {exc}', file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    configure_service_logging('gis_validation-direct')
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'uniquify':
        return _uniquify_main(argv[1:])
    args = _build_parser().parse_args(argv)

    try:
        result = GISValidationApplicationService.run_validation(
            buildings_set=args.buildings_set,
            census_data_csv=args.census_data_csv,
            census_code_field_title=args.census_code_field_title,
            census_units_num_title=args.census_units_num_title,
            postal_code_key=args.postal_code_key,
            function_key=args.function_key,
            function_value=args.function_value,
            cleaned_units_num_key=args.cleaned_units_num_key,
            area_key=args.area_key,
            floor_num_key=args.floor_num_key,
            height_key=args.height_key,
            area_calculation_mode=args.area_calculation_mode,
            include_height_proxy=args.include_height_proxy,
            height_proxy_area_key=args.height_proxy_area_key,
            height_proxy_area_fallback_key=(
                args.height_proxy_area_fallback_key),
            height_proxy_area_fallback_value=(
                args.height_proxy_area_fallback_value),
            unique_attribute_key=args.unique_attribute_key,
            uniquification_area_key=args.uniquification_area_key,
            uniquified_output_path=args.uniquified_output_path,
            census_avg_area_by_type=_load_census_avg_area(
                args.census_avg_area_json),
            output_mode=args.output_mode,
            district_name=args.district_name,
            output_dir=args.output_dir,
            csv_path=args.csv_path,
            include_plot=args.plot,
            plot_path=args.plot_path,
            plot_title=args.plot_title,
            plot_metric=args.plot_metric)
    except Exception as exc:
        logger.error('Direct jug_gis_validation execution failed. Error=%s',
                     exc)
        return 1

    print(f'District codes: {len(result.codes)}')
    print(
        f'Area calculation mode: {result.area_calculation_mode.value}; '
        f'height proxy included={result.height_proxy_included}; '
        f'height proxy area={result.height_proxy_area_key}')
    height_proxy_stats = result.height_proxy_area_resolution_stats
    if height_proxy_stats is not None:
        print(
            'Height proxy area resolution: '
            f'primary={height_proxy_stats.primary_features}, '
            f'fallback={height_proxy_stats.fallback_features}, '
            f'fallback_pct={height_proxy_stats.fallback_percentage:.2f}, '
            f'fallback_type={height_proxy_stats.fallback_type}, '
            f'fallback_key={height_proxy_stats.fallback_key}, '
            f'fallback_value={height_proxy_stats.fallback_value}')
    stats = result.uniquification_stats
    print(
        'Feature uniquification: '
        f'applied={stats.applied}, input={stats.input_features}, '
        f'ranking_area={stats.ranking_area_key}, '
        f'retained={stats.retained_features}, '
        f'removed={stats.removed_features}, '
        f'duplicate_groups={stats.duplicate_groups}')
    if result.csv_path is not None:
        print(f'CSV output: {result.csv_path}')
    if result.plot_path is not None:
        print(f'Plot output: {result.plot_path}')
    if result.uniquified_output_path is not None:
        print(f'Uniquified GeoJSON: {result.uniquified_output_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
