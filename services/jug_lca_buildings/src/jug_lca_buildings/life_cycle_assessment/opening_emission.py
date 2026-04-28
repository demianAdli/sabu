"""
Sabu project
jug_lca_buildings package
opening_emission module
Returns the summarize of all surfaces openings' emissions
The returned value will be used to calculate the building component emission.
Project Designer and Developer: Alireza Adli
Theoritical Support: Mohammad Reza Seyedabadi 
Licensed under the Apache License, Version 2.0.
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""


class OpeningEmission:
  def __init__(self, opening_material_emission, opening_surface):
    self._opening_material_emission = opening_material_emission
    self._opening_surface = opening_surface

  @property
  def opening_material_emission(self):
    return self._opening_material_emission

  @property
  def opening_surface(self):
    return self._opening_surface

  def calculate_opening_emission(self):
    return self._opening_material_emission * self._opening_surface
