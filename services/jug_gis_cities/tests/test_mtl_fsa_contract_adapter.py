"""
Sabu project
jug_gis_cities package
test_mtl_fsa_contract_adapter module
"""
import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_SABU_CHASSIS_SRC = os.path.join(_REPO_ROOT, 'libs', 'sabu_chassis', 'src')
if _SABU_CHASSIS_SRC not in sys.path:
    sys.path.insert(0, _SABU_CHASSIS_SRC)


def _import_contract_adapter(adapter_cls, output_dir):
    fake_citygisoo = types.ModuleType('citygisoo')
    fake_citygisoo.BuildingContractAdapter = adapter_cls
    module_names = [
        'src.jug_gis_cities.mtl_fsa_gisoo.contract_adapter',
        'src.jug_gis_cities.mtl_fsa_gisoo.workflow_config',
    ]
    with patch.dict(
            os.environ,
            {
                'JUG_GIS_CITIES_MTL_FSA_OUTPUT_DIR': output_dir,
                'JUG_GIS_CITIES_QGIS_PATH': 'C:/QGIS',
            }):
        with patch.dict(sys.modules, {'citygisoo': fake_citygisoo}):
            package = sys.modules.get(
                'src.jug_gis_cities.mtl_fsa_gisoo')
            if package is not None:
                package.__dict__.pop('contract_adapter', None)
                package.__dict__.pop('workflow_config', None)
            for module_name in module_names:
                sys.modules.pop(module_name, None)
            return importlib.import_module(module_names[0])


class TestMtlFsaContractAdapter(unittest.TestCase):
    def test_uses_geopackage_and_requested_contract_field_order(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            adapter_cls_mock = Mock()
            adapter_cls_mock.return_value.run.return_value = 'output.geojson'
            contract_adapter = _import_contract_adapter(
                adapter_cls_mock, tmp_dir)

            result = contract_adapter.run_contract_adapter('h3h')

        self.assertEqual(result, 'output.geojson')
        kwargs = adapter_cls_mock.call_args.kwargs
        self.assertEqual(
            kwargs['input_layer_path'],
            os.path.join(
                tmp_dir, 'H3H', 'mtl_H3H_gisoo',
                'mtl_H3H_gisoo.gpkg'))
        self.assertEqual(kwargs['input_layer_name'], 'mtl_H3H_gisoo')
        self.assertEqual(
            kwargs['output_geojson_path'],
            os.path.join(
                tmp_dir, 'H3H', 'mtl_H3H_gisoo_standardized',
                'mtl_H3H_gisoo_standardized.geojson'))
        self.assertEqual(
            kwargs['output_geopackage_path'],
            os.path.join(
                tmp_dir, 'H3H', 'mtl_H3H_gisoo_standardized',
                'mtl_H3H_gisoo_standardized.gpkg'))
        self.assertEqual(
            kwargs['output_layer_name'],
            'mtl_H3H_gisoo_standardized')
        self.assertEqual(
            kwargs['field_order'],
            list(contract_adapter.rename_fields.values()))
        self.assertEqual(kwargs['field_fallback'], ('function', 'usage_function'))
        self.assertIsNone(kwargs['non_null_required_fields'])
        self.assertEqual(
            kwargs['field_order'][:5],
            [
                'citygisoo_id',
                'processing_tool',
                'processed_by',
                'FSA',
                'citygisoo_area',
            ])

    def test_passes_optional_non_null_fields_to_adapter(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            adapter_cls_mock = Mock()
            adapter_cls_mock.return_value.run.return_value = 'output.geojson'
            contract_adapter = _import_contract_adapter(
                adapter_cls_mock, tmp_dir)

            contract_adapter.run_contract_adapter(
                'h3h',
                non_null_required_fields=['citygisoo_id', 'FSA'])

        kwargs = adapter_cls_mock.call_args.kwargs
        self.assertEqual(
            kwargs['non_null_required_fields'],
            ['citygisoo_id', 'FSA'])


if __name__ == '__main__':
    unittest.main()
