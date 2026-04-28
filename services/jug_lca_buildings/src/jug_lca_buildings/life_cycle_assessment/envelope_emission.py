"""
Sabu project
jug_ee project
jug_ee package
envelope_emission module
Project Designer and Developer: Alireza Adli
Theoritical Support for LCA emissions: Mohammad Reza Seyedabadi
Licensed under the Apache License, Version 2.0.
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""


class EnvelopeEmission:
  def __init__(self,
               envelope_material_emission,
               envelope_thickness,
               envelope_surface,
               density):
    self._envelope_material_emission = envelope_material_emission
    self._envelope_thickness = envelope_thickness
    self._envelope_surface = envelope_surface
    self._density = density

  @property
  def envelope_material_emission(self):
    return self._envelope_material_emission

  @property
  def envelope_thickness(self):
    return self._envelope_thickness

  @property
  def envelope_surface(self):
    return self._envelope_surface

  @property
  def density(self):
    return self._density

  def calculate_envelope_emission(self):
    return self._envelope_material_emission * \
           self._envelope_thickness * \
           self._envelope_surface * \
           self._density
