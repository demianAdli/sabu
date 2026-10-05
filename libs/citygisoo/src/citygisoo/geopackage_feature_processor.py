"""
CityGISOO
geopackage_feature_processor module

Python-first feature and table operations for GeoPackage vector layers.
Project Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import os
import uuid
from dataclasses import dataclass
from collections import defaultdict

from qgis.core import (
  QgsDistanceArea,
  QgsFeature,
  QgsFeatureRequest,
  QgsField,
  QgsProject,
  QgsVectorDataProvider,
  QgsVectorFileWriter,
  QgsVectorLayer,
  QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

from sabu_chassis.logging import get_logger


try:
  from qgis.core import NULL as QGIS_NULL
except ImportError:
  QGIS_NULL = None


logger = get_logger(__name__)


@dataclass(frozen=True)
class FieldSpec:
  """Field definition for Python-generated attributes."""

  name: str
  field_type: object = None
  length: int = 0
  precision: int = 0


class GeoPackageFeatureProcessor:
  """Python-first operations for GeoPackage vector layers.

  The processor keeps geometry/topology algorithms out of scope. It is meant
  for attribute filtering, membership tests, grouping, joins, and calculated
  fields where explicit Python logic is easier to control than QGIS
  expressions.
  """

  _SUPPORTED_AGGREGATES = {
    'count',
    'first_value',
    'minimum',
    'maximum',
    'sum',
  }

  def _resolve_layer(self, layer_or_scrub_layer):
    return getattr(layer_or_scrub_layer, 'layer', layer_or_scrub_layer)

  def _layer_name(self, layer_or_scrub_layer, fallback='layer'):
    layer_name = getattr(layer_or_scrub_layer, 'layer_name', None)
    if layer_name:
      return layer_name

    layer = self._resolve_layer(layer_or_scrub_layer)
    name = getattr(layer, 'name', None)
    if callable(name):
      return name()
    return fallback

  def _validate_output_path(self, output_path):
    if os.path.splitext(str(output_path))[1].lower() != '.gpkg':
      raise ValueError(
        'GeoPackageFeatureProcessor only writes GeoPackage outputs.')

  def _validate_input_layer(self, layer_or_scrub_layer):
    layer_path = getattr(layer_or_scrub_layer, 'layer_path', None)
    if layer_path is None:
      layer = self._resolve_layer(layer_or_scrub_layer)
      source = getattr(layer, 'source', None)
      if callable(source):
        layer_path = source()

    if not layer_path:
      return

    normalized_path = str(layer_path).split('|', 1)[0]
    if os.path.splitext(normalized_path)[1].lower() != '.gpkg':
      raise ValueError(
        'GeoPackageFeatureProcessor only accepts GeoPackage input layers.')

  def _field_index(self, layer, field_name):
    field_idx = layer.fields().indexFromName(field_name)
    if field_idx == -1:
      raise KeyError(f'Field {field_name} was not found.')
    return field_idx

  def _request_for_fields(self, layer, field_names, include_geometry=True):
    request = QgsFeatureRequest()
    field_indexes = [
      self._field_index(layer, field_name)
      for field_name in field_names
    ]
    if hasattr(request, 'setSubsetOfAttributes'):
      try:
        request.setSubsetOfAttributes(field_indexes, layer.fields())
      except TypeError:
        request.setSubsetOfAttributes(list(field_names), layer.fields())
    if not include_geometry and hasattr(QgsFeatureRequest, 'NoGeometry'):
      request.setFlags(QgsFeatureRequest.NoGeometry)
    return request

  def _iter_features(
          self,
          layer,
          field_names=None,
          include_geometry=True):
    if field_names:
      request = self._request_for_fields(
        layer,
        field_names,
        include_geometry=include_geometry)
      return layer.getFeatures(request)
    return layer.getFeatures()

  def _feature_value(self, feature, field_name):
    return feature[field_name]

  @staticmethod
  def is_null_value(value):
    """Return True for Python, Qt, and PyQGIS NULL attribute values."""
    if value is None:
      return True
    if QGIS_NULL is not None:
      try:
        if value == QGIS_NULL:
          return True
      except TypeError:
        pass

    is_null = getattr(value, 'isNull', None)
    if callable(is_null) and is_null():
      return True

    is_valid = getattr(value, 'isValid', None)
    if callable(is_valid) and not is_valid():
      return True

    return False

  @classmethod
  def is_not_null_value(cls, value):
    return not cls.is_null_value(value)

  def _write_options(self, output_path, layer_name=None):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.fileEncoding = 'utf-8'
    if layer_name:
      options.layerName = layer_name

    if hasattr(options, 'actionOnExistingFile'):
      overwrite_action = getattr(
        QgsVectorFileWriter,
        'CreateOrOverwriteFile',
        None)
      if overwrite_action is not None:
        options.actionOnExistingFile = overwrite_action

    return options

  def _raise_on_writer_error(self, writer_result, output_path):
    writer_error = (
      writer_result[0]
      if isinstance(writer_result, tuple)
      else writer_result)
    if writer_error != QgsVectorFileWriter.NoError:
      raise RuntimeError(
        f'Failed to write GeoPackage layer to {output_path}: '
        f'{writer_result}')

  def _write_features_like_source(
          self,
          source_layer,
          features,
          output_path,
          layer_name=None):
    self._validate_output_path(output_path)
    feature_ids = [feature.id() for feature in features]

    if not hasattr(source_layer, 'selectByIds'):
      raise TypeError(
        'Source layer must support selectByIds() for feature extraction.')

    source_layer.selectByIds(feature_ids)
    options = self._write_options(output_path, layer_name=layer_name)
    options.onlySelectedFeatures = True
    writer_v3 = getattr(QgsVectorFileWriter, 'writeAsVectorFormatV3', None)
    try:
      if callable(writer_v3):
        result = writer_v3(
          source_layer,
          output_path,
          QgsProject.instance().transformContext(),
          options)
      else:
        result = QgsVectorFileWriter.writeAsVectorFormat(
          source_layer,
          output_path,
          options)
    finally:
      remove_selection = getattr(source_layer, 'removeSelection', None)
      if callable(remove_selection):
        remove_selection()

    self._raise_on_writer_error(result, output_path)
    logger.info(
      'Wrote %s features from %s to %s.',
      len(feature_ids),
      self._layer_name(source_layer),
      output_path)
    return output_path

  def _memory_uri_like(self, source_layer):
    geometry_name = QgsWkbTypes.displayString(source_layer.wkbType())
    crs = source_layer.crs()
    authid = crs.authid() if crs and callable(getattr(crs, 'authid', None)) \
      else ''
    if authid:
      return f'{geometry_name}?crs={authid}'
    return geometry_name

  def _write_memory_layer(self, memory_layer, output_path, layer_name=None):
    self._validate_output_path(output_path)
    options = self._write_options(output_path, layer_name=layer_name)
    writer_v3 = getattr(QgsVectorFileWriter, 'writeAsVectorFormatV3', None)
    if callable(writer_v3):
      result = writer_v3(
        memory_layer,
        output_path,
        QgsProject.instance().transformContext(),
        options)
    else:
      result = QgsVectorFileWriter.writeAsVectorFormat(
        memory_layer,
        output_path,
        options)

    self._raise_on_writer_error(result, output_path)
    return output_path

  def _build_output_field(self, field_spec):
    field_type = field_spec.field_type
    if field_type is None:
      field_type = QVariant.Double
    return QgsField(
      field_spec.name,
      field_type,
      len=field_spec.length,
      prec=field_spec.precision)

  def _area_measure(self, layer):
    measure = QgsDistanceArea()
    project = QgsProject.instance()
    transform_context = project.transformContext()
    crs = layer.crs() if callable(getattr(layer, 'crs', None)) else None
    if crs is not None:
      measure.setSourceCrs(crs, transform_context)

    ellipsoid = (
      project.ellipsoid()
      if callable(getattr(project, 'ellipsoid', None))
      else None)
    if not ellipsoid or str(ellipsoid).upper() == 'NONE':
      ellipsoid = 'WGS84'
    measure.setEllipsoid(ellipsoid)
    return measure

  def extract_by_membership(
          self,
          source_layer,
          lookup_layer,
          source_field,
          lookup_field,
          output_path,
          include_matches=True,
          layer_name=None):
    """Extract features by exact membership in another layer field."""
    self._validate_input_layer(source_layer)
    self._validate_input_layer(lookup_layer)
    source_qgs_layer = self._resolve_layer(source_layer)
    lookup_qgs_layer = self._resolve_layer(lookup_layer)

    lookup_values = {
      self._feature_value(feature, lookup_field)
      for feature in self._iter_features(
        lookup_qgs_layer,
        [lookup_field],
        include_geometry=False)
    }
    kept_features = []
    for feature in self._iter_features(source_qgs_layer, [source_field]):
      is_match = self._feature_value(feature, source_field) in lookup_values
      if is_match == include_matches:
        kept_features.append(feature)

    logger.info(
      'Extracted %s features from %s by membership of %s in %s.%s.',
      len(kept_features),
      self._layer_name(source_layer),
      source_field,
      self._layer_name(lookup_layer),
      lookup_field)
    return self._write_features_like_source(
      source_qgs_layer,
      kept_features,
      output_path,
      layer_name=layer_name)

  def extract_where(
          self,
          source_layer,
          predicate,
          output_path,
          layer_name=None):
    """Extract source features for which predicate(feature) is truthy."""
    self._validate_input_layer(source_layer)
    if not callable(predicate):
      raise TypeError('predicate must be callable.')

    source_qgs_layer = self._resolve_layer(source_layer)
    kept_features = [
      feature
      for feature in self._iter_features(source_qgs_layer)
      if predicate(feature)
    ]
    return self._write_features_like_source(
      source_qgs_layer,
      kept_features,
      output_path,
      layer_name=layer_name)

  def extract_unique_by_field(
          self,
          source_layer,
          field_name,
          output_path,
          include_null=True,
          layer_name=None):
    """Extract the first feature for each distinct field value."""
    self._validate_input_layer(source_layer)
    source_qgs_layer = self._resolve_layer(source_layer)
    seen_values = set()
    kept_features = []
    for feature in self._iter_features(source_qgs_layer, [field_name]):
      value = self._feature_value(feature, field_name)
      if self.is_null_value(value) and not include_null:
        continue
      if value in seen_values:
        continue
      seen_values.add(value)
      kept_features.append(feature)

    return self._write_features_like_source(
      source_qgs_layer,
      kept_features,
      output_path,
      layer_name=layer_name)

  def add_calculated_field(
          self,
          layer,
          field_spec,
          calculator,
          overwrite=False,
          batch_size=10000):
    """Add or update one field using a Python calculator(feature)."""
    self._validate_input_layer(layer)
    if batch_size <= 0:
      raise ValueError('batch_size must be greater than zero.')
    if not callable(calculator):
      raise TypeError('calculator must be callable.')
    if isinstance(field_spec, str):
      field_spec = FieldSpec(field_spec)

    qgs_layer = self._resolve_layer(layer)
    provider = qgs_layer.dataProvider()
    field_idx = qgs_layer.fields().indexFromName(field_spec.name)
    if field_idx != -1 and not overwrite:
      raise ValueError(f'Field {field_spec.name} already exists.')

    if field_idx == -1:
      if not provider.capabilities() & QgsVectorDataProvider.AddAttributes:
        raise ValueError('Layer does not support adding fields.')
      if not provider.addAttributes([self._build_output_field(field_spec)]):
        raise RuntimeError(f'Failed to add field {field_spec.name}.')
      qgs_layer.updateFields()
      field_idx = qgs_layer.fields().indexFromName(field_spec.name)

    if not provider.capabilities() & QgsVectorDataProvider.ChangeAttributeValues:
      raise ValueError('Layer does not support changing attribute values.')

    updated_count = 0
    change_map = {}
    for feature in qgs_layer.getFeatures():
      change_map[feature.id()] = {field_idx: calculator(feature)}
      if len(change_map) >= batch_size:
        if not provider.changeAttributeValues(change_map):
          raise RuntimeError(f'Failed to update field {field_spec.name}.')
        updated_count += len(change_map)
        change_map = {}

    if change_map:
      if not provider.changeAttributeValues(change_map):
        raise RuntimeError(f'Failed to update field {field_spec.name}.')
      updated_count += len(change_map)

    logger.info(
      'Assigned Python-calculated values to field %s on %s for %s features.',
      field_spec.name,
      self._layer_name(layer),
      updated_count)
    return field_spec.name

  def add_area_field(
          self,
          layer,
          field_name,
          overwrite=False,
          batch_size=10000):
    """Add or update a square-meter area field using QGIS measurement."""
    qgs_layer = self._resolve_layer(layer)
    measure = self._area_measure(qgs_layer)
    return self.add_calculated_field(
      layer,
      FieldSpec(field_name, QVariant.Double),
      lambda feature: measure.measureArea(feature.geometry()),
      overwrite=overwrite,
      batch_size=batch_size)

  def add_ratio_field(
          self,
          layer,
          target_field,
          numerator_field,
          denominator_field,
          overwrite=False,
          batch_size=10000):
    """Add or update target_field as numerator_field / denominator_field."""
    qgs_layer = self._resolve_layer(layer)
    self._field_index(qgs_layer, numerator_field)
    self._field_index(qgs_layer, denominator_field)

    def _ratio(feature):
      numerator = self._feature_value(feature, numerator_field)
      denominator = self._feature_value(feature, denominator_field)
      if self.is_null_value(denominator) or denominator == 0:
        return None
      return float(numerator) / float(denominator)

    return self.add_calculated_field(
      layer,
      FieldSpec(target_field, QVariant.Double),
      _ratio,
      overwrite=overwrite,
      batch_size=batch_size)

  def _aggregate_value(self, features, aggregate_function, input_field):
    values = [
      self._feature_value(feature, input_field)
      for feature in features
    ]
    non_null_values = [
      value
      for value in values
      if self.is_not_null_value(value)
    ]

    if aggregate_function == 'count':
      return len(features)
    if aggregate_function == 'first_value':
      return values[0] if values else None
    if aggregate_function == 'minimum':
      return min(non_null_values) if non_null_values else None
    if aggregate_function == 'maximum':
      return max(non_null_values) if non_null_values else None
    if aggregate_function == 'sum':
      return sum(non_null_values) if non_null_values else None

    raise ValueError(f'Unsupported aggregate {aggregate_function}.')

  def aggregate_by_group(
          self,
          source_layer,
          group_field,
          aggregates,
          output_path,
          layer_name=None):
    """Create a GeoPackage table grouped by one field."""
    self._validate_input_layer(source_layer)
    source_qgs_layer = self._resolve_layer(source_layer)
    self._field_index(source_qgs_layer, group_field)
    if not aggregates:
      raise ValueError('At least one aggregate definition is required.')

    normalized_aggregates = []
    for aggregate_definition in aggregates:
      aggregate_function = (
        aggregate_definition.get('aggregate_function')
        or aggregate_definition.get('aggregate'))
      if aggregate_function not in self._SUPPORTED_AGGREGATES:
        raise ValueError(f'Unsupported aggregate {aggregate_function}.')
      output_field = (
        aggregate_definition.get('output_field')
        or aggregate_definition.get('name'))
      input_field = (
        aggregate_definition.get('input_field')
        or aggregate_definition.get('input_expression')
        or aggregate_definition.get('input'))
      if not output_field or not input_field:
        raise ValueError(
          'Aggregate definitions require output_field and input_field.')
      normalized_aggregates.append({
        'output_field': output_field,
        'aggregate_function': aggregate_function,
        'input_field': str(input_field).strip('"'),
        'field_type': aggregate_definition.get('field_type')
        or aggregate_definition.get('type')
        or QVariant.Double,
        'length': aggregate_definition.get('length', 0),
        'precision': aggregate_definition.get('precision', 0),
      })

    grouped_features = defaultdict(list)
    for feature in source_qgs_layer.getFeatures():
      grouped_features[self._feature_value(feature, group_field)].append(
        feature)

    table_layer_name = layer_name or os.path.splitext(
      os.path.basename(output_path))[0]
    output_layer = QgsVectorLayer('None', table_layer_name, 'memory')
    output_provider = output_layer.dataProvider()
    output_fields = [
      QgsField(
        aggregate_definition['output_field'],
        aggregate_definition['field_type'],
        len=aggregate_definition['length'],
        prec=aggregate_definition['precision'])
      for aggregate_definition in normalized_aggregates
    ]
    output_provider.addAttributes(output_fields)
    output_layer.updateFields()

    output_features = []
    for features in grouped_features.values():
      output_feature = QgsFeature(output_layer.fields())
      output_feature.setAttributes([
        self._aggregate_value(
          features,
          aggregate_definition['aggregate_function'],
          aggregate_definition['input_field'])
        for aggregate_definition in normalized_aggregates
      ])
      output_features.append(output_feature)

    output_provider.addFeatures(output_features)
    return self._write_memory_layer(
      output_layer,
      output_path,
      layer_name=table_layer_name)

  def join_attributes(
          self,
          source_layer,
          lookup_layer,
          source_field,
          lookup_field,
          join_fields,
          output_path,
          prefix='',
          layer_name=None):
    """Write source features with selected lookup attributes joined by field."""
    self._validate_input_layer(source_layer)
    self._validate_input_layer(lookup_layer)
    source_qgs_layer = self._resolve_layer(source_layer)
    lookup_qgs_layer = self._resolve_layer(lookup_layer)
    self._field_index(source_qgs_layer, source_field)
    self._field_index(lookup_qgs_layer, lookup_field)
    for join_field in join_fields:
      self._field_index(lookup_qgs_layer, join_field)

    lookup_rows = {}
    lookup_request_fields = [lookup_field] + list(join_fields)
    for lookup_feature in self._iter_features(
            lookup_qgs_layer,
            lookup_request_fields,
            include_geometry=False):
      key = self._feature_value(lookup_feature, lookup_field)
      if key not in lookup_rows:
        lookup_rows[key] = {
          join_field: self._feature_value(lookup_feature, join_field)
          for join_field in join_fields
        }

    joined_layer_name = layer_name or os.path.splitext(
      os.path.basename(output_path))[0]
    output_layer = QgsVectorLayer(
      self._memory_uri_like(source_qgs_layer),
      joined_layer_name,
      'memory')
    output_provider = output_layer.dataProvider()
    output_provider.addAttributes(source_qgs_layer.fields())
    join_output_fields = []
    lookup_fields = lookup_qgs_layer.fields()
    for join_field in join_fields:
      lookup_idx = lookup_fields.indexFromName(join_field)
      lookup_field_def = lookup_fields[lookup_idx]
      join_output_fields.append(QgsField(
        f'{prefix}{join_field}',
        lookup_field_def.type(),
        len=lookup_field_def.length(),
        prec=lookup_field_def.precision()))
    output_provider.addAttributes(join_output_fields)
    output_layer.updateFields()

    output_features = []
    for source_feature in source_qgs_layer.getFeatures():
      key = self._feature_value(source_feature, source_field)
      joined_values = lookup_rows.get(key, {})
      output_feature = QgsFeature(output_layer.fields())
      output_feature.setGeometry(source_feature.geometry())
      output_feature.setAttributes(
        source_feature.attributes()
        + [
          joined_values.get(join_field)
          for join_field in join_fields
        ])
      output_features.append(output_feature)

    output_provider.addFeatures(output_features)
    return self._write_memory_layer(
      output_layer,
      output_path,
      layer_name=joined_layer_name)
