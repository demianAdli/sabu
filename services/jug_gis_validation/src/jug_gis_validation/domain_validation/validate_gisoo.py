"""
Sabu project
jug_gis_validation project
jug_gis_validation package
validate_gisoo module
ValidateGISOO class supports an interactove workflow
to validate cleaned geospatial data.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
https://demianadli.com/
Update considerations:
- Python>=3.8 need to be added to the requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from importlib.resources import as_file, files
from pathlib import Path

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter
from sabu_chassis.logging import get_logger

from jug_gis_validation.errors import (
  GISValidationCalculationError,
  GISValidationDataContractError,
  GISValidationInputError,
)
from .buildings_input import (
  load_buildings_set,
  geojson_text_to_geodataframe,
  geojson_to_geodataframe,
)
from .query_census_data_csv import QueryCensusDataCSV
from .district_geojson_analysis import DistrictGeoJSONAnalysis
from .uniquify_features import (
  FeatureUniquificationStats,
  uniquify_features,
)


logger = get_logger(__name__)
DEFAULT_CENSUS_RESOURCE = 'filtered_census.csv'
DEFAULT_CENSUS_DATA_CSV = f'data/{DEFAULT_CENSUS_RESOURCE}'
DEFAULT_HEIGHT_PROXY_AREA_FALLBACK_VALUE = 80.0


class AreaCalculationMode(str, Enum):
  """Supported ways to derive each feature's validation area."""

  NONE = 'none'
  AREA_ONLY = 'area-only'
  AREA_TIMES_FLOOR = 'area-times-floor'

  @classmethod
  def normalize(cls, value):
    if isinstance(value, cls):
      return value
    if isinstance(value, str):
      try:
        return cls(value.strip().lower())
      except ValueError as exc:
        valid_modes = ', '.join(mode.value for mode in cls)
        raise ValueError(
          f'Unsupported area calculation mode: {value}. '
          f'Supported modes: {valid_modes}.') from exc
    raise TypeError(
      'area_calculation_mode must be a string or AreaCalculationMode.')


@dataclass(frozen=True)
class HeightProxyAreaResolutionStats:
  """Audit statistics for height-proxy base-area resolution."""

  primary_area_key: str
  fallback_type: str
  fallback_key: str | None
  fallback_value: float | None
  evaluated_features: int
  primary_features: int
  fallback_features: int
  fallback_percentage: float
  unresolved_features: int

  def as_dict(self):
    return {
      'primary_area_key': self.primary_area_key,
      'fallback_type': self.fallback_type,
      'fallback_key': self.fallback_key,
      'fallback_value': self.fallback_value,
      'evaluated_features': self.evaluated_features,
      'primary_features': self.primary_features,
      'fallback_features': self.fallback_features,
      'fallback_percentage': self.fallback_percentage,
      'unresolved_features': self.unresolved_features,
    }


class ValidateGISOO:
  def __init__(self, buildings_set,
               census_code_field_title, census_units_num_title,
               postal_code_key, function_key, function_value,
               area_key, floor_num_key,
               census_data_csv=DEFAULT_CENSUS_DATA_CSV,
               census_avg_area_by_type=None,
               height_key='height',
               unique_attribute_key=None,
               uniquification_area_key=None,
               cleaned_units_num_key=None,
               area_calculation_mode=AreaCalculationMode.AREA_TIMES_FLOOR,
               include_height_proxy=False,
               height_proxy_area_key=None,
               height_proxy_area_fallback_key=None,
               height_proxy_area_fallback_value=None):
    # Configuration
    self.postal_code_key = postal_code_key
    self.function_key = function_key
    self.function_value = function_value
    self.area_key = area_key
    self.floor_num_key = floor_num_key
    self.height_key = height_key
    self.unique_attribute_key = unique_attribute_key
    self.cleaned_units_num_key = cleaned_units_num_key
    self.uniquification_area_key = (
      self.area_key
      if uniquification_area_key is None
      else uniquification_area_key)
    self.area_calculation_mode = AreaCalculationMode.normalize(
      area_calculation_mode)
    if not isinstance(include_height_proxy, bool):
      raise TypeError('include_height_proxy must be a boolean.')
    if (
      self.area_calculation_mode is AreaCalculationMode.NONE
      and include_height_proxy
    ):
      raise ValueError(
        'include_height_proxy cannot be enabled when '
        'area_calculation_mode is none.')
    self.include_height_proxy = include_height_proxy
    self.height_proxy_area_key = (
      self.area_key
      if height_proxy_area_key is None
      else height_proxy_area_key)
    if (
      height_proxy_area_fallback_key is not None
      and height_proxy_area_fallback_value is not None
    ):
      raise ValueError(
        'height_proxy_area_fallback_key and '
        'height_proxy_area_fallback_value are mutually exclusive.')
    self.height_proxy_area_fallback_key = height_proxy_area_fallback_key
    if self.height_proxy_area_fallback_key is None:
      fallback_value = (
        DEFAULT_HEIGHT_PROXY_AREA_FALLBACK_VALUE
        if height_proxy_area_fallback_value is None
        else height_proxy_area_fallback_value)
      try:
        fallback_value = float(fallback_value)
      except (TypeError, ValueError) as exc:
        raise ValueError(
          'height_proxy_area_fallback_value must be numeric.') from exc
      if not np.isfinite(fallback_value) or fallback_value <= 0:
        raise ValueError(
          'height_proxy_area_fallback_value must be finite and greater '
          'than zero.')
      self.height_proxy_area_fallback_value = fallback_value
    else:
      self.height_proxy_area_fallback_value = None
    self._height_proxy_area_resolution_stats = None
    self.census_code_field_title = census_code_field_title
    self.census_units_num_title = census_units_num_title

    # Clean District Data
    self._load_district, self._buildings_source = self._load_buildings_set(
      buildings_set)
    self._ensure_columns(
      self._load_district,
      self._required_district_columns(),
      'buildings_set')
    if self.unique_attribute_key is None:
      self._uniquification_stats = FeatureUniquificationStats.not_applied(
        len(self._load_district))
    else:
      self._load_district, self._uniquification_stats = uniquify_features(
        self._load_district,
        unique_attribute_key=self.unique_attribute_key,
        area_key=self.uniquification_area_key)
    logger.info(
      'Validation feature uniquification. Applied=%s UniqueAttribute=%s '
      'RankingArea=%s Input=%s Retained=%s Removed=%s DuplicateGroups=%s',
      self._uniquification_stats.applied,
      self._uniquification_stats.unique_attribute_key,
      self._uniquification_stats.ranking_area_key,
      self._uniquification_stats.input_features,
      self._uniquification_stats.retained_features,
      self._uniquification_stats.removed_features,
      self._uniquification_stats.duplicate_groups)
    self._district = DistrictGeoJSONAnalysis(self._load_district)

    district_codes = self._district.return_all_codes(self.postal_code_key)
    self._district_codes = list(district_codes)
    if "Non" in self._district_codes:
      self._district_codes.remove("Non")

    # Validation Data
    self._load_census_data, self._census_source = self._load_census_data_csv(
      census_data_csv)

    self._census_data = QueryCensusDataCSV(
      self._load_census_data,
      self.census_code_field_title,
      self.census_units_num_title,
      area_by_characteristic=census_avg_area_by_type,
      calculate_total_area=(
        self.area_calculation_mode is not AreaCalculationMode.NONE),
    )

    missing_census_codes = sorted(
      set(self._district_codes) - set(self._census_data.units_num.index))
    if missing_census_codes:
      logger.warning(
        'Census data is missing %s district code(s). Sample=%s',
        len(missing_census_codes),
        missing_census_codes[:10])

    if not self._district_codes:
      logger.warning('No district codes were found in buildings_set.')

    logger.info(
      'Initialized GISOO validator. BuildingsSource=%s CensusSource=%s '
      'Features=%s DistrictCodes=%s AreaCalculationMode=%s '
      'IncludeHeightProxy=%s HeightProxyArea=%s HeightProxyFallbackKey=%s '
      'HeightProxyFallbackValue=%s',
      self._buildings_source,
      self._census_source,
      len(self._load_district),
      len(self._district_codes),
      self.area_calculation_mode.value,
      self.include_height_proxy,
      self.height_proxy_area_key if self.include_height_proxy else None,
      self.height_proxy_area_fallback_key,
      self.height_proxy_area_fallback_value)

  # Compatibility aliases for existing callers of the loading helpers.
  _load_buildings_set = staticmethod(load_buildings_set)
  _geojson_text_to_geodataframe = staticmethod(geojson_text_to_geodataframe)
  _geojson_to_geodataframe = staticmethod(geojson_to_geodataframe)

  @staticmethod
  def _load_census_data_csv(census_data_csv) -> tuple[pd.DataFrame, str]:
    if isinstance(census_data_csv, pd.DataFrame):
      return census_data_csv.copy(), 'dataframe'

    read_kwargs = {
      'encoding': 'cp1252',
      'encoding_errors': 'replace',
      'low_memory': False,
    }

    if (
      census_data_csv is None
      or (
        isinstance(census_data_csv, str)
        and census_data_csv in (DEFAULT_CENSUS_DATA_CSV,
                                DEFAULT_CENSUS_RESOURCE)
      )
    ):
      resource = files('jug_gis_validation.data').joinpath(
        DEFAULT_CENSUS_RESOURCE)
      try:
        with as_file(resource) as census_path:
          return pd.read_csv(census_path, **read_kwargs), (
            f'packaged:{DEFAULT_CENSUS_RESOURCE}')
      except FileNotFoundError as exc:
        raise GISValidationInputError(
          f'Packaged census data is missing: {DEFAULT_CENSUS_RESOURCE}'
        ) from exc
      except Exception as exc:
        raise GISValidationInputError(
          f'Unable to read packaged census data: {DEFAULT_CENSUS_RESOURCE}'
        ) from exc

    if hasattr(census_data_csv, 'read'):
      try:
        return pd.read_csv(census_data_csv, **read_kwargs), 'file-like'
      except Exception as exc:
        raise GISValidationInputError(
          'Unable to read census_data_csv file-like object.') from exc

    path = Path(census_data_csv).expanduser()
    if not path.exists():
      raise GISValidationInputError(
        f'census_data_csv path does not exist: {path}')

    try:
      return pd.read_csv(path, **read_kwargs), f'path:{path}'
    except Exception as exc:
      raise GISValidationInputError(
        f'Unable to read census_data_csv file: {path}') from exc

  def _required_district_columns(self):
    required_columns = [self.postal_code_key]
    if self.area_calculation_mode is not AreaCalculationMode.NONE:
      required_columns.append(self.area_key)
    if self.area_calculation_mode is AreaCalculationMode.AREA_TIMES_FLOOR:
      required_columns.append(self.floor_num_key)
    if self.include_height_proxy:
      required_columns.append(self.height_key)
      required_columns.append(self.height_proxy_area_key)
      if self.height_proxy_area_fallback_key is not None:
        required_columns.append(self.height_proxy_area_fallback_key)
    if self.function_key is not None:
      required_columns.append(self.function_key)
    if self.unique_attribute_key is not None:
      required_columns.append(self.unique_attribute_key)
      required_columns.append(self.uniquification_area_key)
    if self.cleaned_units_num_key is not None:
      required_columns.append(self.cleaned_units_num_key)
    return required_columns

  @property
  def uniquification_stats(self) -> FeatureUniquificationStats:
    """Statistics for validation-only feature uniquification."""
    return self._uniquification_stats

  @property
  def validation_features(self) -> gpd.GeoDataFrame:
    """Return a copy of the feature snapshot used by validation."""
    return self._load_district.copy()

  @property
  def height_proxy_area_resolution_stats(
          self) -> HeightProxyAreaResolutionStats | None:
    """Area fallback statistics, populated when height proxy is calculated."""
    return self._height_proxy_area_resolution_stats

  def _resolve_height_proxy_areas(self):
    primary_areas = pd.to_numeric(
      self._load_district[self.height_proxy_area_key],
      errors='coerce')
    primary_valid = (
      primary_areas.notna()
      & np.isfinite(primary_areas)
      & primary_areas.gt(0))

    relevant = pd.Series(True, index=self._load_district.index)
    if self.function_key is not None:
      relevant = self._load_district[self.function_key].eq(
        self.function_value)

    fallback_needed = relevant & ~primary_valid
    resolved_areas = primary_areas.copy()
    if self.height_proxy_area_fallback_key is not None:
      fallback_areas = pd.to_numeric(
        self._load_district[self.height_proxy_area_fallback_key],
        errors='coerce')
      fallback_valid = (
        fallback_areas.notna()
        & np.isfinite(fallback_areas)
        & fallback_areas.gt(0))
      unresolved = fallback_needed & ~fallback_valid
      if unresolved.any():
        unresolved_indexes = self._load_district.index[unresolved].tolist()
        raise GISValidationDataContractError(
          'Height-proxy area fallback field '
          f'{self.height_proxy_area_fallback_key!r} contains unusable values '
          'where the primary area is unusable. Input index sample: '
          f'{unresolved_indexes[:10]}')
      resolved_areas.loc[fallback_needed] = fallback_areas.loc[fallback_needed]
      fallback_type = 'field'
      fallback_key = self.height_proxy_area_fallback_key
      fallback_value = None
    else:
      resolved_areas.loc[fallback_needed] = (
        self.height_proxy_area_fallback_value)
      unresolved = pd.Series(False, index=self._load_district.index)
      fallback_type = 'constant'
      fallback_key = None
      fallback_value = self.height_proxy_area_fallback_value

    evaluated_features = int(relevant.sum())
    fallback_features = int(fallback_needed.sum())
    primary_features = evaluated_features - fallback_features
    fallback_percentage = (
      fallback_features * 100.0 / evaluated_features
      if evaluated_features
      else 0.0)
    stats = HeightProxyAreaResolutionStats(
      primary_area_key=self.height_proxy_area_key,
      fallback_type=fallback_type,
      fallback_key=fallback_key,
      fallback_value=fallback_value,
      evaluated_features=evaluated_features,
      primary_features=primary_features,
      fallback_features=fallback_features,
      fallback_percentage=round(fallback_percentage, 2),
      unresolved_features=int(unresolved.sum()),
    )
    return resolved_areas, stats

  @staticmethod
  def _ensure_columns(dataframe, required_columns, dataset_name):
    missing_columns = [
      column for column in required_columns
      if column and column not in dataframe.columns
    ]
    if missing_columns:
      raise GISValidationDataContractError(
        f'{dataset_name} is missing required column(s): '
        f'{", ".join(missing_columns)}')

  def _ensure_code(self, code, dataset):
    if code not in dataset:
      raise GISValidationDataContractError(
        f'District code is not available in validation results: {code}')

  @property
  def district_codes(self):
    """FSA codes present in the district (no 'Non')."""
    # immutable -> no changes in the workflow
    return tuple(self._district_codes)

  @cached_property
  def district_units_num_all_dict(self):
    """dict[FSA] -> cleaned units using feature or configured-field counts."""
    return self._district.summarize_all_codes_units(
      postal_code_key=self.postal_code_key,
      codes=self._district_codes,
      units_num_key=self.cleaned_units_num_key,
      prefix_len=3,
      function_key=self.function_key,
      function_value=self.function_value,
    )

  @cached_property
  def _codes_info(self):
    """
    Internal cached (info, nones_info) for the selected area workflow.

    info: dict[FSA] -> (units_num, total_area)
    nones_info: tuple(units_num_with_None_or_zero, area_with_None_or_zero)
    """
    logger.debug(
      'Computing district code summaries. AreaCalculationMode=%s',
      self.area_calculation_mode.value)
    try:
      if self.area_calculation_mode is AreaCalculationMode.NONE:
        info = {
          code: (units_num, 0.0)
          for code, units_num in self.district_units_num_all_dict.items()
        }
      elif self.area_calculation_mode is AreaCalculationMode.AREA_ONLY:
        area_info = self._district.summarize_all_codes_with_multipliers(
          postal_code_key=self.postal_code_key,
          return_key=self.area_key,
          multipliers=[1.0] * len(self._load_district),
          codes=self._district_codes,
          prefix_len=3,
          function_key=self.function_key,
          function_value=self.function_value,
        )
      else:
        area_info = self._district.summarize_all_codes_dict(
          postal_code_key=self.postal_code_key,
          return_key=self.area_key,
          floor_num_key=self.floor_num_key,
          codes=self._district_codes,
          prefix_len=3,
          function_key=self.function_key,
          function_value=self.function_value,
        )
      if self.area_calculation_mode is not AreaCalculationMode.NONE:
        info = {
          code: (
            self.district_units_num_all_dict[code],
            area_info[code][1],
          )
          for code in area_info
        }
    except GISValidationDataContractError:
      raise
    except Exception as exc:
      raise GISValidationCalculationError(
        'Unable to summarize district codes using area calculation mode '
        f'{self.area_calculation_mode.value}.') from exc

    nones_info = (0, 0)
    if "Non" in info:
      nones_info = info.pop("Non")
      logger.warning(
        'District summary contains features with missing/nonstandard code. '
        'Units=%s Area=%s',
        nones_info[0],
        nones_info[1])

    return info, nones_info

  @property
  def district_codes_info(self):
    """dict[FSA] -> (units_num, total_area) using the selected area mode."""
    return self._codes_info[0]

  @property
  def district_nones(self):
    """(units_with_none_or_zero, area_with_none_or_zero)."""
    return self._codes_info[1]

  @cached_property
  def _codes_info_proxy(self):
    """
    Internal cached (info, nones_info) for height-to-floor proxy workflow.
    """
    logger.debug('Computing district code summaries with height proxy.')
    self._ensure_columns(self._load_district, [self.height_key],
                         'buildings_set')
    try:
      resolved_areas, resolution_stats = self._resolve_height_proxy_areas()
      proxy_info = self._district.height_to_floor_proxy(self.height_key, 3.5)
      multipliers, num_nones, pct_nones, num_zeros, pct_zeros = proxy_info
      if num_nones or num_zeros:
        logger.warning(
          'Height proxy contains missing or zero values. '
          'Missing=%s MissingPct=%.2f Zero=%s ZeroPct=%.2f',
          num_nones,
          pct_nones,
          num_zeros,
          pct_zeros)
      resolved_area_field = '__height_proxy_resolved_area__'
      proxy_district_frame = self._load_district.copy()
      proxy_district_frame[resolved_area_field] = resolved_areas
      proxy_district = DistrictGeoJSONAnalysis(proxy_district_frame)
      area_info = proxy_district.summarize_all_codes_with_multipliers(
        postal_code_key=self.postal_code_key,
        return_key=resolved_area_field,
        multipliers=multipliers,
        codes=self._district_codes,
        prefix_len=3,
        function_key=self.function_key,
        function_value=self.function_value,
      )
      info = {
        code: (
          self.district_units_num_all_dict[code],
          area_info[code][1],
        )
        for code in area_info
      }
      self._height_proxy_area_resolution_stats = resolution_stats
      logger.info(
        'Resolved height-proxy base areas. Primary=%s Fallback=%s '
        'FallbackPct=%.2f FallbackType=%s FallbackKey=%s FallbackValue=%s',
        resolution_stats.primary_features,
        resolution_stats.fallback_features,
        resolution_stats.fallback_percentage,
        resolution_stats.fallback_type,
        resolution_stats.fallback_key,
        resolution_stats.fallback_value)
    except GISValidationDataContractError:
      raise
    except Exception as exc:
      raise GISValidationCalculationError(
        'Unable to summarize district codes with height proxy.') from exc

    nones_info = (0, 0)
    if 'Non' in info:
      nones_info = info.pop('Non')
      logger.warning(
        'Height proxy summary contains features with missing/nonstandard code. '
        'Units=%s Area=%s',
        nones_info[0],
        nones_info[1])

    return info, nones_info

  @cached_property
  def census_total_area_all_dict(self):
    if self.area_calculation_mode is AreaCalculationMode.NONE:
      raise GISValidationCalculationError(
        'Area comparison is disabled for this validation run.')
    areas = self._census_data.total_area.reindex(self._district_codes)
    missing = sorted(areas[areas.isna()].index.tolist())
    if missing:
      logger.warning(
        'Census total area is missing for %s district code(s). Sample=%s',
        len(missing),
        missing[:10])
    return areas.to_dict()

  @property
  def district_codes_info_proxy(self):
    """dict[FSA] -> (units_num, total_area) using height-to-floor proxy."""
    return self._codes_info_proxy[0]

  @property
  def district_nones_proxy(self):
    """(units_with_none_or_zero, area_with_none_or_zero) for proxy workflow."""
    return self._codes_info_proxy[1]

  @cached_property
  def census_units_num_all_dict(self):
    """
    dict[FSA] -> census units count, reindexed to district_codes.
    Uses the units rule:
      - if remaining_dwellings != 0 => Total private dwellings
      - else => Total - Private households by household size - 100% data
    """
    units_num = self._census_data.units_num.reindex(self._district_codes).fillna(0)
    return units_num.to_dict()

  def calculate_codes_unit_frequency_percentage(self):
    district_total_units = sum(
      [index[0] for index in self.district_codes_info.values()])
    if district_total_units == 0:
      raise GISValidationCalculationError(
        'Cannot calculate unit frequency percentages because total district '
        'units is zero.')
    return {code: self.district_codes_info[code][0] * 100 / district_total_units
            for code in self.district_codes_info.keys()}

  def calculate_codes_area_frequency_percentage(self):
    district_total_area = sum(
      [index[1] for index in self.district_codes_info.values()])
    if district_total_area == 0:
      raise GISValidationCalculationError(
        'Cannot calculate area frequency percentages because total district '
        'area is zero.')
    return {code: self.district_codes_info[code][1] * 100 / district_total_area
            for code in self.district_codes_info.keys()}

  def clean_district_vs_census_unit(self, code):
    self._ensure_code(code, self.district_codes_info)
    self._ensure_code(code, self.census_units_num_all_dict)
    clean_district_unit = self.district_codes_info[code][0]
    difference = clean_district_unit - self.census_units_num_all_dict[code]
    if clean_district_unit == 0:
      difference_ratio = 0
    else:
      difference_ratio = abs(difference) * 100 / clean_district_unit
    return difference, difference_ratio

  def clean_districts_vs_census_unit(self, codes=None):
    if codes is None:
      codes = self.district_codes

    all_differences_unit = dict()
    for code in codes:
      all_differences_unit[code] = self.clean_district_vs_census_unit(code)
    return all_differences_unit

  def clean_district_and_census_unit(self, code):
    self._ensure_code(code, self.district_codes_info)
    self._ensure_code(code, self.census_units_num_all_dict)
    return self.district_codes_info[code][0],\
        self.census_units_num_all_dict[code]

  def clean_districts_and_census_unit(self, codes=None):
    if codes is None:
      codes = self.district_codes

    both_units = dict()
    for code in codes:
      both_units[code] = self.clean_district_and_census_unit(code)
    return both_units

  def clean_district_vs_census_area(self, code):
    self._ensure_code(code, self.district_codes_info)
    self._ensure_code(code, self.census_total_area_all_dict)
    clean_district_area = self.district_codes_info[code][1]
    census_units_to_area = self.census_total_area_all_dict[code]
    if pd.isna(census_units_to_area) or census_units_to_area == 0:
      raise GISValidationCalculationError(
        f'Cannot calculate area ratio for {code} because census total area '
        'is missing or zero.')
    difference = clean_district_area - census_units_to_area
    difference_ratio = abs(difference) * 100 / census_units_to_area
    return round(difference, 2), difference_ratio

  def clean_districts_vs_census_area(self, codes=None):
    if codes is None:
      codes = self.district_codes

    all_differences_area = dict()
    for code in codes:
      all_differences_area[code] = \
        self.clean_district_vs_census_area(code)
    return all_differences_area

  def clean_district_and_census_area(self, code):
    self._ensure_code(code, self.district_codes_info)
    self._ensure_code(code, self.census_total_area_all_dict)
    return self.district_codes_info[code][1],\
           self.census_total_area_all_dict[code]

  def clean_districts_and_census_area(self, codes=None):
    if codes is None:
      codes = self.district_codes

    both_areas = dict()
    for code in codes:
      both_areas[code] = \
        self.clean_district_and_census_area(code)
    return both_areas

  @staticmethod
  def plot_area_comparison(
          codes_info,
          areas,
          census_areas,
          *,
          title='Area comparison',
          y_label='Area (m²)',
          x_label=''
  ):
    if not (len(codes_info) == len(areas) == len(census_areas)):
      raise ValueError('codes, areas, and census_areas must have the same length')

    n = len(codes_info)
    x = np.arange(n)
    width = 0.39

    fig, ax = plt.subplots(figsize=(max(5.0, n * 1.2), 4.5))
    ax.bar(x - width / 2, areas, width, label=x_label)
    ax.bar(x + width / 2, census_areas, width, label='Census')

    ax.set_xlabel('Code')
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.set_xticks(x, codes_info)
    ax.legend()

    # Format y-axis with thousands separators
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{int(v):,}'))
    fig.tight_layout()
    return fig, ax

  def comparison_table(self, codes) -> dict:
    table = {
      'FSA': codes,
      'Cleaned Units Num':
        [self.district_codes_info[code][0] for code in codes],
      'Census Units Num':
        [self.census_units_num_all_dict[code] for code in codes],
      'Cleaned vs. Census Units':
        [value[0] for value in
         self.clean_districts_vs_census_unit(codes).values()],
    }
    if self.area_calculation_mode is not AreaCalculationMode.NONE:
      table['Cleaned Total Area'] = [
        self.district_codes_info[code][1] for code in codes
      ]
      table['Census Total Area (by type)'] = [
        self.census_total_area_all_dict[code] for code in codes
      ]
    if self.include_height_proxy:
      table['Cleaned Total Area (height proxy)'] = [
        self.district_codes_info_proxy[code][1] for code in codes
      ]
      resolution_stats = self.height_proxy_area_resolution_stats
      table['Height Proxy Area Fallback Type'] = [
        resolution_stats.fallback_type for _ in codes
      ]
      table['Height Proxy Area Fallback Features'] = [
        resolution_stats.fallback_features for _ in codes
      ]
      table['Height Proxy Area Fallback Percentage'] = [
        resolution_stats.fallback_percentage for _ in codes
      ]
    return table

  def comparison_csv(self, codes, distric_name):
    comparison_df = pd.DataFrame(self.comparison_table(codes))
    comparison_df.to_csv(f'validate_{distric_name}_gi.csv', index=False)
