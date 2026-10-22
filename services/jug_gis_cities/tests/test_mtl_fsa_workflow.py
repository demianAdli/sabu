"""
Sabu project
jug_gis_cities package
test_mtl_fsa_workflow module
Verify Montreal FSA workflow composition and retained provenance.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


_REPO_ROOT = os.path.abspath(
  os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_SABU_CHASSIS_SRC = os.path.join(_REPO_ROOT, 'libs', 'sabu_chassis', 'src')
_JUG_GIS_CITIES_SRC = os.path.join(_REPO_ROOT, 'services', 'jug_gis_cities')
for _path in [_SABU_CHASSIS_SRC, _JUG_GIS_CITIES_SRC]:
  if _path not in sys.path:
    sys.path.insert(0, _path)


class _FakeGeoPackageFeatureProcessor:
  calls = []

  def add_area_field(self, layer, field_name, overwrite=False,
                     batch_size=10000):
    self.calls.append((
      'add_area_field',
      layer.layer_name,
      field_name,
      overwrite,
      batch_size))
    return field_name

  def add_ratio_field(
          self,
          layer,
          target_field,
          numerator_field,
          denominator_field,
          overwrite=False,
          batch_size=10000):
    self.calls.append((
      'add_ratio_field',
      layer.layer_name,
      target_field,
      numerator_field,
      denominator_field,
      overwrite,
      batch_size))
    return target_field

  def aggregate_by_group(
          self,
          source_layer,
          group_field,
          aggregates,
          output_path,
          layer_name=None):
    self.calls.append((
      'aggregate_by_group',
      source_layer.layer_name,
      group_field,
      aggregates,
      output_path,
      layer_name))
    return output_path

  def extract_by_membership(
          self,
          source_layer,
          lookup_layer,
          source_field,
          lookup_field,
          output_path,
          include_matches=True,
          layer_name=None):
    self.calls.append((
      'extract_by_membership',
      source_layer.layer_name,
      lookup_layer.layer_name,
      source_field,
      lookup_field,
      output_path,
      include_matches,
      layer_name))
    return output_path

  def extract_where(self, source_layer, predicate, output_path,
                    layer_name=None):
    self.calls.append((
      'extract_where',
      source_layer.layer_name,
      output_path,
      layer_name))
    return output_path

  def extract_unique_by_field(
          self,
          source_layer,
          field_name,
          output_path,
          include_null=True,
          layer_name=None):
    self.calls.append((
      'extract_unique_by_field',
      source_layer.layer_name,
      field_name,
      output_path,
      include_null,
      layer_name))
    return output_path


class _FakeScrubLayer:
  calls = []
  instances = []

  def __init__(self, qgis_path, layer_path, layer_name):
    self.qgis_path = qgis_path
    self.layer_path = layer_path
    self.layer_name = layer_name
    self.data_count = 1 if layer_name.startswith('fsa_boundary_') else 7
    self.calls.append(('init', qgis_path, layer_path, layer_name))
    self.instances.append(self)

  def extract_by_attribute(self, field_name, operator, value, output_path):
    self.calls.append((
      'extract_by_attribute',
      self.layer_name,
      field_name,
      operator,
      value,
      output_path))
    return output_path

  def add_uuid_field(self, field_name='uuid', field_length=36,
                     overwrite=False):
    self.calls.append((
      'add_uuid_field',
      self.layer_name,
      field_name,
      field_length,
      overwrite))
    return field_name

  def duplicate_layer(self, output_path):
    self.calls.append(('duplicate_layer', self.layer_name, output_path))
    return output_path

  def clip_layer(self, overlay_layer, clipped_layer):
    self.calls.append((
      'clip_layer',
      self.layer_name,
      overlay_layer,
      clipped_layer))
    return clipped_layer

  def fix_geometries(self, output_path):
    self.calls.append(('fix_geometries', self.layer_name, output_path))
    return output_path

  def delete_duplicate_geometries(self, output_path):
    self.calls.append((
      'delete_duplicate_geometries',
      self.layer_name,
      output_path))
    return output_path

  def add_field(self, new_field_name):
    self.calls.append(('add_field', self.layer_name, new_field_name))
    return new_field_name

  def assign_area(self, field_name):
    self.calls.append(('assign_area', self.layer_name, field_name))
    return field_name

  def difference_layer(self, overlay_layer, output_path, grid_size=None):
    self.calls.append((
      'difference_layer',
      self.layer_name,
      overlay_layer.layer_name,
      output_path,
      grid_size))
    return output_path

  def spatial_join_with_predicate(
          self,
          joining_layer_path,
          joined_layer_path,
          predicate='intersect',
          join_method='one-to-many',
          prefix=''):
    self.calls.append((
      'spatial_join_with_predicate',
      self.layer_name,
      joining_layer_path,
      joined_layer_path,
      predicate,
      join_method,
      prefix))
    return joined_layer_path

  def point_on_surface(self, output_path, all_parts=False):
    self.calls.append((
      'point_on_surface',
      self.layer_name,
      output_path,
      all_parts))
    return output_path

  def geometry_by_expression(
          self,
          expression,
          output_path,
          output_geometry_type='polygon',
          with_z=False,
          with_m=False):
    self.calls.append((
      'geometry_by_expression',
      self.layer_name,
      expression,
      output_path,
      output_geometry_type,
      with_z,
      with_m))
    return output_path

  def intersection_layer(
          self,
          overlay_layer,
          output_path,
          input_fields=None,
          overlay_fields=None,
          overlay_fields_prefix=''):
    self.calls.append((
      'intersection_layer',
      self.layer_name,
      overlay_layer.layer_name,
      output_path,
      input_fields,
      overlay_fields,
      overlay_fields_prefix))
    return output_path

  def duplicate_text_field(
          self,
          source_field,
          target_field,
          field_length,
          overwrite=False,
          batch_size=10000):
    self.calls.append((
      'duplicate_text_field',
      self.layer_name,
      source_field,
      target_field,
      field_length,
      overwrite,
      batch_size))
    return target_field

  def assign_field_expression(
          self,
          target_field,
          expression,
          field_type=None,
          field_length=0,
          field_precision=0):
    self.calls.append((
      'assign_field_expression',
      self.layer_name,
      target_field,
      expression,
      field_type,
      field_length,
      field_precision))
    return target_field

  def field_join(
          self,
          joining_layer_path,
          joining_layer_name,
          target_field,
          join_field,
          join_fields=None,
          prefix='',
          output_path=None,
          selected_features_only=False,
          joining_selected_features_only=False,
          join_method=1,
          discard_nonmatching=False,
          unjoinable_output_path=None):
    self.calls.append((
      'field_join',
      self.layer_name,
      joining_layer_path,
      joining_layer_name,
      target_field,
      join_field,
      join_fields,
      prefix,
      output_path,
      selected_features_only,
      joining_selected_features_only,
      join_method,
      discard_nonmatching,
      unjoinable_output_path))
    return output_path

  def add_layer_join(
          self,
          joining_layer_path,
          joining_layer_name,
          join_field,
          target_field,
          prefix='',
          output_path=None,
          join_fields=None,
          selected_features_only=False,
          joining_selected_features_only=False,
          join_method=1,
          discard_nonmatching=False,
          unjoinable_output_path=None):
    self.calls.append((
      'add_layer_join',
      self.layer_name,
      joining_layer_path,
      joining_layer_name,
      join_field,
      target_field,
      prefix,
      output_path,
      join_fields,
      selected_features_only,
      joining_selected_features_only,
      join_method,
      discard_nonmatching,
      unjoinable_output_path))
    return output_path

  @staticmethod
  def merge_layer_paths(layer_paths, output_path, crs=None):
    _FakeScrubLayer.calls.append((
      'merge_layer_paths',
      layer_paths,
      output_path,
      crs))
    return output_path

  def create_spatial_index(self):
    self.calls.append(('create_spatial_index', self.layer_name))

  def keep_only_fields(self, fields_to_keep, strict=True):
    self.calls.append((
      'keep_only_fields',
      self.layer_name,
      fields_to_keep,
      strict))
    return fields_to_keep

  def drop_fields(self, fields_to_drop, strict=True):
    self.calls.append((
      'drop_fields',
      self.layer_name,
      fields_to_drop,
      strict))
    return self

  def __str__(self):
    return f'The {self.layer_name} has {self.data_count} records.'


def _import_mtl_fsa_workflow(data_dir, output_dir):
  fake_citygisoo = types.ModuleType('citygisoo')
  fake_scrub_layer_module = types.ModuleType('citygisoo.scrub_layer_class')
  fake_scrub_layer_module.ScrubLayer = _FakeScrubLayer
  fake_citygisoo.GeoPackageFeatureProcessor = _FakeGeoPackageFeatureProcessor

  module_names = [
    'src.jug_gis_cities.mtl_fsa_gisoo.workflow',
    'src.jug_gis_cities.mtl_fsa_gisoo.workflow_config',
  ]
  with patch.dict(
          os.environ,
          {
            'JUG_GIS_CITIES_MTL_FSA_DATA_DIR': data_dir,
            'JUG_GIS_CITIES_MTL_FSA_OUTPUT_DIR': output_dir,
            'JUG_GIS_CITIES_QGIS_PATH': 'C:/QGIS',
          }):
    with patch.dict(
            sys.modules,
            {
              'citygisoo': fake_citygisoo,
              'citygisoo.scrub_layer_class': fake_scrub_layer_module,
            }):
      for module_name in module_names:
        sys.modules.pop(module_name, None)
      return importlib.import_module(module_names[0])


class TestMtlFsaWorkflow(unittest.TestCase):
  def setUp(self):
    _FakeGeoPackageFeatureProcessor.calls = []
    _FakeScrubLayer.calls = []
    _FakeScrubLayer.instances = []

  def test_run_workflow_transfers_nrcan_intersection_tail(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      data_dir = os.path.join(temp_dir, 'data')
      output_dir = os.path.join(temp_dir, 'output')
      workflow = _import_mtl_fsa_workflow(data_dir, output_dir)

      result = workflow.run_workflow('h3h')

    def _output_path(output_key):
      return os.path.join(
        output_dir,
        'H3H',
        output_key,
        f'{output_key}.gpkg')

    fsa_boundary_path = _output_path('fsa_boundary')
    nrcan_preserved_path = _output_path('nrcan_preserved')
    usage_dup_path = _output_path('usage_dup')
    nrcan_path = _output_path('nrcan')
    roll_path = _output_path('roll')
    usage_path = _output_path('usage')
    nrcan_fixed_path = _output_path('nrcan_fixed')
    nrcan_preserved_fixed_path = _output_path('nrcan_preserved_fixed')
    usage_fixed_path = _output_path('usage_fixed')
    usage_dup_fixed_path = _output_path('usage_dup_fixed')
    usage_margin_san_path = _output_path('usage_margin_san')
    usage_clean_path = _output_path('usage_clean')
    usage_margin_path = _output_path('usage_margin')
    usage_only_path = _output_path('usage_only')
    roll_only_path = _output_path('roll_only')
    usage_roll_only_all_path = _output_path('usage_roll_only_all')
    usage_roll_only_path = _output_path('usage_roll_only')
    usage_roll_only_unique_path = _output_path('usage_roll_only_unique')
    roll_clean_path = _output_path('roll_clean')
    usage_roll_path = _output_path('usage_roll')
    usage_roll_all_path = _output_path('usage_roll_all')
    usage_dup_clean_path = _output_path('usage_dup_clean')
    inter_nrcan_path = _output_path('inter_nrcan')
    inter_summary_path = _output_path('inter_summary')
    summary_joined_path = _output_path('summary_joined')
    inter_kept_path = _output_path('inter_kept')
    nrcan_joined_summary_path = _output_path('nrcan_joined_summary')
    nrcan_restored_path = _output_path('nrcan_restored')
    dominant_parts_path = _output_path('dominant_parts')
    nrcan_restored_with_usage_id_path = _output_path(
      'nrcan_restored_with_usage_id')
    nrcan_intersected_path = _output_path('nrcan_intersected')
    nrcan_intersected_points_path = _output_path('nrcan_intersected_points')
    nrcan_in_usage_roll_points_path = _output_path(
      'nrcan_in_usage_roll_points')
    nrcan_usage_roll_with_missing_path = _output_path(
      'nrcan_usage_roll_with_missing')
    usage_roll_all_only_path = _output_path('usage_roll_all_only')
    nrcan_usage_roll_path = _output_path('nrcan_usage_roll')
    final_output_key = 'mtl_H3H_gisoo'
    final_output_path = _output_path(final_output_key)

    self.assertEqual(result, final_output_path)
    self.assertNotIn(
      'add_uuid_field',
      [call[0] for call in _FakeScrubLayer.calls])
    self.assertNotIn(
      'duplicate_layer',
      [call[0] for call in _FakeScrubLayer.calls])

    self.assertIn(
      (
        'init',
        'C:/QGIS',
        os.path.join(
          data_dir,
          'input_data',
          'mamh_usage_predo_2026_gpkg',
          'mamh_usage_predo_2026_s_poly.gpkg'),
        'usage_mtl',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'init',
        'C:/QGIS',
        os.path.join(
          data_dir,
          'input_data',
          'mtl_auto_with_heights_preserved',
          'mtl_auto_with_heights_preserved.gpkg'),
        'nrcan_preserved_mtl',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'init',
        'C:/QGIS',
        os.path.join(
          data_dir,
          'input_data',
          'mamh_usage_predo_2026_gpkg_dup',
          'mamh_usage_predo_2026_dup.gpkg'),
        'usage_dup_mtl',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'extract_by_attribute',
        'fsa_boundaries',
        'g_fsa',
        '=',
        'H3H',
        fsa_boundary_path,
      ),
      _FakeScrubLayer.calls)

    for layer_name, output_path in [
            ('nrcan_mtl', nrcan_path),
            ('nrcan_preserved_mtl', nrcan_preserved_path),
            ('roll_mtl', roll_path),
            ('usage_mtl', usage_path),
            ('usage_dup_mtl', usage_dup_path)]:
      self.assertIn(
        (
          'clip_layer',
          layer_name,
          fsa_boundary_path,
          output_path,
        ),
        _FakeScrubLayer.calls)

    self.assertIn(
      (
        'fix_geometries',
        'nrcan_clipped_H3H',
        nrcan_fixed_path,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'add_area_field',
        'nrcan_fixed_H3H',
        'nrcan_area',
        False,
        10000,
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'init',
        'C:/QGIS',
        nrcan_fixed_path,
        'nrcan_fixed_H3H',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'fix_geometries',
        'nrcan_preserved_H3H',
        nrcan_preserved_fixed_path,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'add_area_field',
        'nrcan_preserved_fixed_H3H',
        'nrcan_area',
        False,
        10000,
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'init',
        'C:/QGIS',
        nrcan_preserved_fixed_path,
        'nrcan_preserved_fixed_H3H',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'fix_geometries',
        'usage_clipped_H3H',
        usage_fixed_path,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'fix_geometries',
        'usage_dup_H3H',
        usage_dup_fixed_path,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'delete_duplicate_geometries',
        'usage_dup_fixed_H3H',
        usage_dup_clean_path,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'extract_by_membership',
        'usage_fixed_H3H',
        'roll_clipped_H3H',
        'g_id_provi',
        'id_provinc',
        usage_margin_san_path,
        False,
        'usage_margin_san_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'difference_layer',
        'usage_clipped_H3H',
        'usage_margin_san_H3H',
        usage_clean_path,
        None,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'extract_where',
        'usage_margin_san_H3H',
        usage_margin_path,
        'usage_margin_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'add_area_field',
        'usage_margin_H3H',
        'area_ex',
        False,
        10000,
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'extract_where',
        'usage_margin_H3H',
        usage_only_path,
        'usage_only_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'extract_by_membership',
        'roll_clipped_H3H',
        'usage_clipped_H3H',
        'id_provinc',
        'g_id_provi',
        roll_only_path,
        False,
        'roll_only_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'spatial_join_with_predicate',
        'usage_clipped_H3H',
        roll_only_path,
        usage_roll_only_all_path,
        'contains',
        'one-to-many',
        'ro_',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'extract_where',
        'usage_roll_only_all_H3H',
        usage_roll_only_path,
        'usage_roll_only_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'extract_unique_by_field',
        'usage_roll_only_H3H',
        'ro_id_provinc',
        usage_roll_only_unique_path,
        False,
        'usage_roll_only_unique_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'difference_layer',
        'roll_clipped_H3H',
        'roll_only_H3H',
        roll_clean_path,
        None,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'duplicate_text_field',
        'roll_clean_H3H',
        'id_provinc',
        'r_id_provinc',
        36,
        False,
        10000,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'add_layer_join',
        'usage_clean_H3H',
        roll_clean_path,
        'roll_clean_H3H',
        'r_id_provinc',
        'g_id_provi',
        'r_',
        usage_roll_path,
        None,
        False,
        False,
        1,
        False,
        None,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'merge_layer_paths',
        [
          usage_roll_path,
          usage_only_path,
          usage_roll_only_unique_path,
        ],
        usage_roll_all_path,
        None,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'assign_field_expression',
        'usage_roll_all_H3H',
        'usage_roll_id',
        "replace(replace(uuid(), '{', ''), '}', '')",
        10,
        36,
        0,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'intersection_layer',
        'nrcan_fixed_H3H',
        'usage_dup_clean_H3H',
        inter_nrcan_path,
        None,
        ['usage_id'],
        '',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'add_area_field',
        'inter_nrcan_H3H',
        'inter_area',
        False,
        10000,
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'add_ratio_field',
        'inter_nrcan_H3H',
        'area_ratio',
        'inter_area',
        'nrcan_area',
        False,
        10000,
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    aggregate_calls = [
      call for call in _FakeGeoPackageFeatureProcessor.calls
      if call[0] == 'aggregate_by_group'
    ]
    self.assertEqual(
      aggregate_calls[0][1:3],
      ('inter_nrcan_H3H', 'nrcan_id'))
    self.assertEqual(aggregate_calls[0][4], inter_summary_path)
    self.assertEqual(aggregate_calls[0][5], 'inter_summary_H3H')
    self.assertIn(
      (
        'assign_field_expression',
        'inter_summary_H3H',
        'restore_group',
        (
          'CASE\n'
          'WHEN\n'
          '    "number_parts" > 1\n'
          '    AND "min_inter_area" < 30\n'
          '    AND "max_area_ratio" >= 0.70\n'
          'THEN 1\n'
          'WHEN\n'
          '    "number_parts" >= 3\n'
          '    AND "nrcan_area" <= 75\n'
          '    AND "max_inter_area" < 30\n'
          '    AND "sum_area_ratio" >= 0.95\n'
          'THEN 1\n'
          'ELSE 0\n'
          'END'),
        2,
        0,
        0,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'field_join',
        'inter_nrcan_H3H',
        inter_summary_path,
        'inter_summary_H3H',
        'nrcan_id',
        'nrcan_id',
        [
          'restore_group',
          'restore_reason',
          'number_parts',
          'min_inter_area',
          'max_inter_area',
          'max_area_ratio',
        ],
        'sum_',
        summary_joined_path,
        False,
        False,
        'first match',
        False,
        None,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'extract_where',
        'summary_joined_H3H',
        inter_kept_path,
        'inter_kept_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'field_join',
        'nrcan_preserved_fixed_H3H',
        inter_summary_path,
        'inter_summary_H3H',
        'nrcan_id',
        'nrcan_id',
        [
          'restore_group',
          'restore_reason',
        ],
        '',
        nrcan_joined_summary_path,
        False,
        False,
        1,
        False,
        None,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'extract_where',
        'nrcan_joined_summary_H3H',
        nrcan_restored_path,
        'nrcan_restored_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'extract_where',
        'summary_joined_H3H',
        dominant_parts_path,
        'dominant_parts_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'field_join',
        'nrcan_restored_H3H',
        dominant_parts_path,
        'dominant_parts_H3H',
        'nrcan_id',
        'nrcan_id',
        ['usage_id'],
        '',
        nrcan_restored_with_usage_id_path,
        False,
        False,
        1,
        False,
        None,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'merge_layer_paths',
        [
          inter_kept_path,
          nrcan_restored_with_usage_id_path,
        ],
        nrcan_intersected_path,
        None,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'assign_field_expression',
        'c_nrcan_intersected_H3H',
        'nrcan_in_id',
        "replace(replace(uuid(), '{', ''), '}', '')",
        10,
        36,
        0,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'point_on_surface',
        'c_nrcan_intersected_H3H',
        nrcan_intersected_points_path,
        False,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'spatial_join_with_predicate',
        'nrcan_intersected_points',
        usage_roll_all_path,
        nrcan_in_usage_roll_points_path,
        'within',
        'one-to-many',
        'ur_',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'geometry_by_expression',
        'nrcan_in_usage_roll_points_H3H',
        (
          "geometry(\n"
          "    get_feature(\n"
          "        'c_nrcan_intersected_H3H',\n"
          "        'nrcan_in_id',\n"
          "        attribute(@feature, 'nrcan_in_id')\n"
          "    )\n"
          ")"),
        nrcan_usage_roll_with_missing_path,
        'polygon',
        False,
        False,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'init',
        'C:/QGIS',
        nrcan_usage_roll_with_missing_path,
        'nrcan_usage_roll_with_missing',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'extract_by_membership',
        'usage_roll_all_H3H',
        'nrcan_usage_roll_with_missing',
        'id_provinc',
        'ur_id_provinc',
        usage_roll_all_only_path,
        False,
        'usage_roll_all_only_H3H',
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'init',
        'C:/QGIS',
        usage_roll_all_only_path,
        'usage_roll_all_only_H3H',
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'merge_layer_paths',
        [
          nrcan_usage_roll_with_missing_path,
          usage_roll_all_only_path,
        ],
        nrcan_usage_roll_path,
        None,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'init',
        'C:/QGIS',
        nrcan_usage_roll_path,
        'nrcan_usage_roll_H3H',
      ),
      _FakeScrubLayer.calls)
    # The workflow preserves merged source fields for adaptation and tracing;
    # it no longer invokes the old (currently empty) field-deletion list.
    self.assertFalse(any(
      call[0] == 'drop_fields' and call[1] == 'nrcan_usage_roll_H3H'
      for call in _FakeScrubLayer.calls))
    self.assertIn(
      (
        'assign_field_expression',
        'nrcan_usage_roll_H3H',
        'FSA',
        "'H3H'",
        10,
        3,
        0,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'assign_field_expression',
        'nrcan_usage_roll_H3H',
        'citygisoo_id',
        "replace(replace(uuid(), '{', ''), '}', '')",
        10,
        36,
        0,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'add_area_field',
        'nrcan_usage_roll_H3H',
        'citygisoo_area',
        False,
        10000,
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'assign_field_expression',
        'nrcan_usage_roll_H3H',
        'processing_tool',
        "'citygisoo'",
        10,
        32,
        0,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'assign_field_expression',
        'nrcan_usage_roll_H3H',
        'processed_by',
        "'Sabu GIS Cities'",
        10,
        32,
        0,
      ),
      _FakeScrubLayer.calls)
    self.assertIn(
      (
        'extract_where',
        'nrcan_usage_roll_H3H',
        final_output_path,
        final_output_key,
      ),
      _FakeGeoPackageFeatureProcessor.calls)
    self.assertIn(
      (
        'init',
        'C:/QGIS',
        final_output_path,
        final_output_key,
      ),
      _FakeScrubLayer.calls)


if __name__ == '__main__':
  unittest.main()
