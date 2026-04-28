"""
Sabu project
jug_lca_buildings package
test_opening_emission module
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
from unittest import TestCase
from src.jug_lca_buildings.life_cycle_assessment.opening_emission\
    import OpeningEmission


class TestOpeningEmission(TestCase):
    def setUp(self):
        self.opening = OpeningEmission(230, 13)

    def test_calculate_opening_emission(self):
        expected = 230 * 13
        self.assertEqual(self.opening.calculate_opening_emission(), expected)
