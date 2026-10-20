"""Building-input loading shared by validation and standalone uniquification."""
from __future__ import annotations

import json
from os import PathLike
from pathlib import Path
from typing import Any

import geopandas as gpd

from jug_gis_validation.errors import GISValidationInputError


def load_buildings_set(
    buildings_set, *, preserve_geojson_values=False,
) -> tuple[gpd.GeoDataFrame, str]:
  """Load a snapshot; optionally parse files exactly like inline GeoJSON.

  Validation retains its existing GDAL file reader. Standalone uniquification
  uses JSON parsing to avoid driver coercion of mixed identifier/area values
  and promotion of top-level feature IDs into properties.
  """
  if isinstance(buildings_set, gpd.GeoDataFrame):
    return buildings_set.copy(), 'geodataframe'

  if isinstance(buildings_set, dict):
    return geojson_to_geodataframe(
      buildings_set), 'geojson-dict'

  if isinstance(buildings_set, list):
    return geojson_to_geodataframe(
      buildings_set), 'feature-list'

  if hasattr(buildings_set, 'read'):
    try:
      raw_content = buildings_set.read()
    except Exception as exc:
      raise GISValidationInputError(
        'Unable to read buildings_set file-like object.') from exc
    return (
      geojson_text_to_geodataframe(raw_content),
      'file-like')

  if isinstance(buildings_set, (str, PathLike)):
    if isinstance(buildings_set, str):
      candidate_text = buildings_set.strip()
      if candidate_text.startswith(('{', '[')):
        return (
          geojson_text_to_geodataframe(candidate_text),
          'geojson-string')

    path = Path(buildings_set).expanduser()
    if not path.exists():
      raise GISValidationInputError(
        f'buildings_set path does not exist: {path}')

    try:
      if preserve_geojson_values:
        return (
          geojson_text_to_geodataframe(path.read_text(encoding='utf-8')),
          f'path:{path}')
      return gpd.read_file(path), f'path:{path}'
    except Exception as exc:
      raise GISValidationInputError(
        f'Unable to read buildings_set GeoJSON file: {path}') from exc

  raise GISValidationInputError(
    'buildings_set must be a GeoDataFrame, GeoJSON dict/string, feature '
    'list, file-like object, or path to a GeoJSON file.')

def geojson_text_to_geodataframe(raw_content) -> gpd.GeoDataFrame:
  if isinstance(raw_content, bytes):
    raw_content = raw_content.decode('utf-8')

  if not isinstance(raw_content, str):
    raise GISValidationInputError(
      'GeoJSON file-like content must be text or bytes.')

  try:
    geojson_obj = json.loads(raw_content)
  except json.JSONDecodeError as exc:
    raise GISValidationInputError(
      'buildings_set content is not valid GeoJSON JSON text.') from exc

  return geojson_to_geodataframe(geojson_obj)

def geojson_to_geodataframe(geojson_obj: Any) -> gpd.GeoDataFrame:
  if isinstance(geojson_obj, dict):
    geojson_type = geojson_obj.get('type')
    if geojson_type == 'FeatureCollection':
      features = geojson_obj.get('features')
    elif geojson_type == 'Feature':
      features = [geojson_obj]
    else:
      raise GISValidationInputError(
        'GeoJSON object must be a FeatureCollection or Feature.')
  elif isinstance(geojson_obj, list):
    features = geojson_obj
  else:
    raise GISValidationInputError(
      'GeoJSON content must be a FeatureCollection, Feature, or feature list.')

  if not isinstance(features, list):
    raise GISValidationInputError('GeoJSON features must be a list.')

  try:
    return gpd.GeoDataFrame.from_features(features)
  except Exception as exc:
    raise GISValidationInputError(
      'Unable to convert buildings_set GeoJSON features to a GeoDataFrame.'
    ) from exc

