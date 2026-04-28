"""
Sabu project
jug_lca_buildings package
jug_ee package
access_nrcan_catalog module
Project Designer and Developer: Alireza Adli
Licensed under the Apache License, Version 2.0.
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import json
from pathlib import Path

from hub.helpers.data.hub_function_to_nrcan_construction_function \
  import HubFunctionToNrcanConstructionFunction


class AccessNrcanCatalog:
  def __init__(
          self, path,
          archetypes='nrcan_archetypes.json',
          constructions='nrcan_constructions_cap_3.json',
          materials='nrcan_materials_dictionaries.json',
          transparent_surfaces='nrcan_transparent_surfaces_dictionaries.json'):
    """
      AccessNrcanCatalog eases accessing the below json files.
      - It converts year of construction to the period of construction.
      - It searches a specific material or transparent surface.
      - The class finds the opaque surface code based on three parameters.
      :param path: path to the below files
      :param archetypes: a json file (a list of dictionaries) with building
      archetypes' data
      :param constructions: a json file (a list of dictionaries) with
      building data based on NRCan
      :param materials: a json file (a dictornaty of
      dictionares to speed up the search) with construction material info.
      :param transparent_surfaces: a json file (a dictionary of
      dictionaries) with windows and skylights data.
    """
    self._path = Path(path)
    self.archetypes = archetypes
    self.constructions = constructions
    self.materials = materials
    self.transparent_surfaces = transparent_surfaces
    self.hub_to_nrcan_dictionary = \
        HubFunctionToNrcanConstructionFunction().dictionary

  @property
  def archetypes(self):
    return self._archetypes

  @archetypes.setter
  def archetypes(self, archetypes):
    archetypes_path = (self._path / archetypes).resolve()
    self._archetypes = json.loads(archetypes_path.read_text())

  @property
  def constructions(self):
    return self._constructions

  @constructions.setter
  def constructions(self, constructions):
    constructions_path = (self._path / constructions).resolve()
    self._constructions = json.loads(constructions_path.read_text())

  @property
  def materials(self):
    return self._materials

  @materials.setter
  def materials(self, materials):
    materials_path = (self._path / materials).resolve()
    self._materials = json.loads(materials_path.read_text())

  @property
  def transparent_surfaces(self):
    return self._transparent_surfaces

  @transparent_surfaces.setter
  def transparent_surfaces(self, transparent_surfaces):
    transparent_surfaces_path = (self._path / transparent_surfaces).resolve()
    self._transparent_surfaces = json.loads(
      transparent_surfaces_path.read_text())

  def hub_to_nrcan_function(self, hub_function):
    return self.hub_to_nrcan_dictionary[hub_function]

  @staticmethod
  def year_to_period_of_construction(year_of_construction):
    """
      Converts year of construction to the period of construction.
      :param year_of_construction: int
      :return: str
    """
    period_of_construction = None
    if 1000 <= year_of_construction <= 1900:
      period_of_construction = '1000_1900'
    elif 1901 <= year_of_construction <= 1910:
      period_of_construction = '1901_1910'
    elif 1911 <= year_of_construction <= 1920:
      period_of_construction = '1911_1920'
    elif 1921 <= year_of_construction <= 1930:
      period_of_construction = '1921_1930'
    elif 1931 <= year_of_construction <= 1940:
      period_of_construction = '1931_1940'
    elif 1941 <= year_of_construction <= 1950:
      period_of_construction = '1941_1950'
    elif 1951 <= year_of_construction <= 1960:
      period_of_construction = '1951_1960'
    elif 1961 <= year_of_construction <= 1970:
      period_of_construction = '1961_1970'
    elif 1971 <= year_of_construction <= 1980:
      period_of_construction = '1971_1980'
    elif 1981 <= year_of_construction <= 1990:
      period_of_construction = '1981_1990'
    elif 1991 <= year_of_construction <= 2000:
      period_of_construction = '1991_2000'
    elif 2001 <= year_of_construction <= 2010:
      period_of_construction = '2001_2010'
    elif 2011 <= year_of_construction <= 2016:
      period_of_construction = '2011_2016'
    elif 2017 <= year_of_construction <= 2019:
      period_of_construction = '2017_2019'
    elif 2020 <= year_of_construction <= 3000:
      period_of_construction = '2020_3000'
    return period_of_construction

  def layers(self, opaque_surface_code, component_type):
    """
      Returns the corresponding layers of a specific opaque surface
      and the component type.
      :param opaque_surface_code: str
      :param component_type: str
      :return: dict
    """
    for opaque_surface in self.constructions['opaque_surfaces']:
      opaque_surface_key = list(opaque_surface)[0]
      if opaque_surface_key != opaque_surface_code:
        continue
      elif opaque_surface[opaque_surface_key]['type'] == component_type:
        return opaque_surface[opaque_surface_key]['layers']

  def search_material(self, material_name):
    """
      Search materials and bring up the specific material data
      based on the material's name
      :param material_name: str
      :return: dict
    """
    return self.materials[f'{material_name}']

  def search_transparent_surfaces(
          self, surface_type, opaque_surface_code):
    """
      Search transparent surfaces and bring up the specific surface data
      based on its type and opaque surface code
      :param surface_type: str
      :param opaque_surface_code: str
      :return: dict
    """
    return self.transparent_surfaces[
      f'{surface_type}_{opaque_surface_code}']

  def find_opaque_surface(
          self, function, period_of_construction, climate_zone):
    """
      Returns the opaque_surface_name based on the below parameters.
      :param function: str
      :param period_of_construction: str
      :param climate_zone: str
      :return: str
    """
    for archetype in self.archetypes['archetypes']:
      if archetype['function'] != function:
        continue
      elif archetype['period_of_construction'] != period_of_construction:
        continue
      elif archetype['climate_zone'] != climate_zone:
        continue
      else:
        return \
          archetype['constructions']['OutdoorsWall']['opaque_surface_name']
