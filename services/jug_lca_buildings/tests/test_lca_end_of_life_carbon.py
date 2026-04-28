"""
Sabu project
jug_lca_buildings package
test_lca_end_of_life_carbon module
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
from unittest import TestCase
from unittest.mock import MagicMock

from src.jug_lca_buildings.life_cycle_assessment.lca_end_of_life_carbon\
    import EndOfLifeEmission


DEMOLITION = 4.3577325
ONSITE = 2.0576313
COMPANY = 0.6189555
LANDFILL = 15.7364044


class TestLCAEndOfLife(TestCase):
    def setUp(self):
        self.lca_eol = EndOfLifeEmission(
            0.9, 0, 1, 0.1, 13,
            demolition_machine_emission=DEMOLITION,
            onsite_machine_emission=ONSITE,
            companies_recycling_machine_emission=COMPANY,
            landfilling_machine_emission=LANDFILL)

    def test_demolition(self):
        self.assertAlmostEqual(
            self.lca_eol.demolition(), DEMOLITION * 13, places=6)

    def test_onsite_recycling(self):
        self.assertAlmostEqual(
            self.lca_eol.onsite_recycling(),
            0.9 * (0.0 * ONSITE * 13), places=6)

    def test_companies_recycling(self):
        self.assertAlmostEqual(
            self.lca_eol.companies_recycling(),
            0.9 * (1.0 * COMPANY * 13), places=6)

    def test_landfilling(self):
        self.assertAlmostEqual(
            self.lca_eol.landfilling(),
            0.1 * LANDFILL * 13, places=6)

    def test_calculate_end_of_life_emission(self):
        self.lca_eol.demolition = MagicMock(return_value=10.0)
        self.lca_eol.onsite_recycling = MagicMock(return_value=2.5)
        self.lca_eol.companies_recycling = MagicMock(return_value=3.0)
        self.lca_eol.landfilling = MagicMock(return_value=4.5)

        total = self.lca_eol.calculate_end_of_life_emission()

        self.assertEqual(total, 10.0 + 2.5 + 3.0 + 4.5)
        self.lca_eol.demolition.assert_called_once()
        self.lca_eol.onsite_recycling.assert_called_once()
        self.lca_eol.companies_recycling.assert_called_once()
        self.lca_eol.landfilling.assert_called_once()
