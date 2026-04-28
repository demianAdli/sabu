"""
Sabu project
jug_lca_buildings package
test_machine module
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
from unittest import TestCase
from src.jug_lca_buildings.life_cycle_assessment.machine\
    import Machine


class TestMachine(TestCase):
    def setUp(self):
        self.machine = Machine(
            machine_id=1,
            name="Excavator",
            work_efficiency_rate=2.0,
            work_efficiency_unit="m3/h",
            energy_consumption_rate=5.0,
            energy_consumption_unit="kWh",
            emission_factor=0.1,
            emission_unit="kgCO2/kWh"
        )

    def test_total_machine_emission(self):
        expected = 2.0 * 5.0 * 0.1
        self.assertEqual(self.machine.total_machine_emssion(), expected)
