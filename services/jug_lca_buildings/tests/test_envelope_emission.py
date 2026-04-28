"""
Sabu project
jug_lca_buildings package
test_envelope_emission module
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
from unittest import TestCase
from src.jug_lca_buildings.life_cycle_assessment.envelope_emission\
    import EnvelopeEmission


class TestEnvelopeEmission(TestCase):
    def setUp(self):
        self.envelope = EnvelopeEmission(230, 0.2, 13, 2.3)

    def test_calculate_envelope_emission(self):
        expected = 230 * 0.2 * 13 * 2.3
        self.assertEqual(self.envelope.calculate_envelope_emission(), expected)
