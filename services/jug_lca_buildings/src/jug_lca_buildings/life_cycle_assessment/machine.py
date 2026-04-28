"""
Sabu project
jug_lca_buildings package
machine module
Project Designer and Developer: Alireza Adli
Theoritical Support for LCA emissions: Mohammad Reza Seyedabadi
Licensed under the Apache License, Version 2.0.
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""


class Machine:
  def __init__(self, machine_id, name, work_efficiency_rate,
               work_efficiency_unit, energy_consumption_rate,
               energy_consumption_unit, emission_factor,
               emission_unit):
    self._machine_id = machine_id
    self._name = name
    self._work_efficiency_rate = work_efficiency_rate
    self._work_efficiency_unit = work_efficiency_unit
    self._energy_consumption_rate = energy_consumption_rate
    self._energy_consumption_unit = energy_consumption_unit
    self._emission_factor = emission_factor
    self._emission_unit = emission_unit

  @property
  def id(self) -> int:
    return self._machine_id

  @property
  def name(self):
    return self._name

  @property
  def work_efficiency(self):
    return self._work_efficiency_rate

  @property
  def work_efficiency_unit(self):
    return self._work_efficiency_unit

  @property
  def energy_consumption_rate(self):
    return self._energy_consumption_rate

  @property
  def energy_consumption_unit(self):
    return self._energy_consumption_unit

  @property
  def emission_factor(self):
    return self._emission_factor

  @property
  def emission_unit(self):
    return self._emission_unit

  def total_machine_emssion(self):
    return self._work_efficiency_rate * \
        self._energy_consumption_rate * \
        self._emission_factor
