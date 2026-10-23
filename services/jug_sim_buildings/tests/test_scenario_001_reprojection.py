"""
Sabu project
jug_sim_buildings package
test_scenario_001_reprojection module
Verify reprojection capability gates and final export invariants.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
import sys
import types
import unittest
from unittest.mock import patch

from jug_sim_buildings.scenario_001.reprojection import check_capability, verify_final
from test_scenario_001_preparation import feature


class TestReprojectionContract(unittest.TestCase):
    def test_missing_or_incompatible_method_fails_even_with_package_importable(self):
        for cls in (type('ScrubLayer', (), {}), type('ScrubLayer', (), {
                'reproject_layer': lambda self, target_crs, output_path: output_path})):
            module = types.ModuleType('citygisoo')
            module.ScrubLayer = cls
            with patch.dict(sys.modules, {'citygisoo': module}), self.assertRaises(RuntimeError):
                check_capability()

    def test_final_export_checks_ids_attributes_metrics_geometry_and_axis_bounds(self):
        original = feature()
        verify_final([deepcopy(original)], [original], equivalent=True)
        changes = [lambda f: f.update(id=999),
                   lambda f: f['properties'].update(citygisoo_area=0),
                   lambda f: f['geometry'].update(type='MultiPolygon'),
                   lambda f: f['geometry']['coordinates'][0][0].__setitem__(1, 200)]
        for change in changes:
            broken = deepcopy(original)
            change(broken)
            with self.assertRaises((ValueError, TypeError)):
                verify_final([broken], [original])
