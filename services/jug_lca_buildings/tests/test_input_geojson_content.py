"""
Sabu project
jug_lca_buildings package
test_input_geojson_content module
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import os
import json
import unittest
from src.jug_lca_buildings.life_cycle_assessment.input_geojson_content\
    import InputGeoJsonContent


class TestInputGeoJsonContent(unittest.TestCase):
    def test_content_as_string(self):
        path_str = "/path/to/file.geojson"
        geo = InputGeoJsonContent(path_str)
        self.assertEqual(geo.content, path_str)

    def test_content_as_dict(self):
        data = {"type": "FeatureCollection", "features": []}
        geo = InputGeoJsonContent(data)

        # _content should now be a temp file path
        self.assertTrue(os.path.exists(geo.content))
        self.assertTrue(geo.content.endswith(".geojson"))

        # File should contain the same JSON
        with open(geo.content, "r", encoding="utf8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded, data)

        os.remove(geo.content)
