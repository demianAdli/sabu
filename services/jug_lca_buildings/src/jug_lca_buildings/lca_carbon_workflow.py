"""
Sabu project
jug_lca_buildings package
lca_carbon_workflow module
Currently calculates Embodied and End-of-Life
Returns the summarize of envelope and energy systems
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import logging
import os
from pathlib import Path
from time import perf_counter

from hub.imports.geometry_factory import GeometryFactory
from hub.imports.construction_factory import ConstructionFactory
from hub.helpers.dictionaries import Dictionaries

from .life_cycle_assessment.input_geojson_content import InputGeoJsonContent
from .life_cycle_assessment.access_nrcan_catalogue import AccessNrcanCatalog
from .life_cycle_assessment.opening_emission import OpeningEmission
from .life_cycle_assessment.envelope_emission import EnvelopeEmission
from .life_cycle_assessment.lca_end_of_life_carbon import EndOfLifeEmission


logger = logging.getLogger(__name__)


def _env_int(name, default, minimum=1):
  try:
    value = int(os.getenv(name, str(default)))
  except (TypeError, ValueError):
    return default
  return max(minimum, value)


class LCACarbonWorkflow:
  def __init__(
          self,
          city_path,
          archetypes_catalog_file_name,
          constructions_catalog_file,
          catalog='nrcan',
          building_parameters=('height', 'year_of_construction', 'function')):
    """
      LCACarbonWorkflow takes a number of buildings and enrich the city object
      using cerc-hub GeometryFactory and ConstructionFactory. Then it
      calculates embodied and end of life carbon emission of each building.
      It puts out the results of opening and envelop emission for each
      mentioned cycle separately.
      Final results will be stored in the below attributes:
        building_envelope_emission: float
        building_opening_emission: float
        building_component_emission: float
        building_envelope_end_of_life_emission: float
        building_opening_end_of_life_emission:  float
        building_component_end_of_life_emission: float

      The above attributes will be computed when the calculate_emission()
      method of a LCACarbonWorkflow object is called.

      :param city_path: Either a path to the buildings (GeoJson)
      file or the content of such a file.
      :param archetypes_catalog_file_name: Path to the buildings'
      archetypes (JSON).
      :param constructions_catalog_file: Path to the construction materials
      data.
      :param catalog: Type of the catalog (in this case 'nrcan', the default
       argument)
      :param building_parameters: Parameters used for using the catalog (in
      this case three default arguments)
    """
    city_input = InputGeoJsonContent(city_path)
    city_candidate = city_input.content
    p = Path(city_candidate)
    used_package_data_fallback = False
    if not p.is_absolute() and not p.exists():
      p = Path(__file__).parent / 'data' / p
      used_package_data_fallback = True
    try:
      self.file_path = p.resolve()
    except OSError:
      self.file_path = p
    if city_input.is_temp_file:
      logger.info('City input resolved to a temporary GeoJSON file.')
    elif used_package_data_fallback:
      logger.info('City input resolved under package data.')
    elif self.file_path.exists():
      logger.info('City input resolved to an existing path.')
    else:
      logger.debug('City input path resolved.')
    logger.debug(f'City input path: {self.file_path}')
    if not city_input.is_temp_file and not self.file_path.exists():
      raise FileNotFoundError(
        f'City input file not found after normalization: {self.file_path}'
      )

    self.catalogs_path = Path(__file__).parent / 'data'
    self.archetypes_catalog_file_name = archetypes_catalog_file_name
    self.constructions_catalog_file = constructions_catalog_file
    self.nrcan_catalogs = AccessNrcanCatalog(
      self.catalogs_path,
      archetypes=self.archetypes_catalog_file_name,
      constructions=self.constructions_catalog_file)
    self.out_path = (Path(__file__).parent / 'out_files')
    self.handler = catalog
    self.height, self.year_of_construction, self.function = \
        building_parameters
    self.progress_log_every = _env_int('LCA_PROGRESS_LOG_EVERY', 100)

    logger.info('Calculation started...')

    try:
      city_t0 = perf_counter()
      self.city = GeometryFactory(
                'geojson',
                path=self.file_path,
                height_field=self.height,
                year_of_construction_field=self.year_of_construction,
                function_field=self.function,
                function_to_hub=Dictionaries().
                montreal_function_to_hub_function
            ).city
      logger.info(f'City was created from {self.file_path}')
      logger.info(
        f'City geometry parsing took {perf_counter() - city_t0:.3f}s')
    except (FileNotFoundError, ValueError, OSError) as e:
      logger.error(f'Failed to create city from {self.file_path}: {e}')
      raise RuntimeError(
       f'Invalid building input data: '
       f'could not create city from {self.file_path}'
            ) from e

    enrich_t0 = perf_counter()
    ConstructionFactory(self.handler, self.city).enrich()
    logger.info(
      f'Construction enrichment took {perf_counter() - enrich_t0:.3f}s')

    logger.info(f'There are {len(self.city.buildings)} buildings in the city.')
    logger.debug('City was enriched with construction data.')

    self.building_envelope_emission = []
    self.building_opening_emission = []
    self.building_component_emission = []
    self.building_envelope_end_of_life_emission = []
    self.building_opening_end_of_life_emission = []
    self.building_component_end_of_life_emission = []

  def calculate_building_component_emission(self, building):
    """
      This method is the core of the whole class. It takes each building
      contained in the city object and calculates and returns the envelope
      and opening emission of the embodied and end of life cycles. The building
      comes from the calculate_emission() method which goes through every
      building of the city object (meaning the input of the LCACarbonWorkflow
      object.
      The calculate_building_component_emission() method goes through each
      surface of the given building then each boundary of that surface to
      calculate the embodied and end of life emission of openings and the
      envelope of the building. It is being carried out by utilizing to
      hidden methods of the current class (methods contain description.)
      At the end, a tuple will be returned, containing the emissions
      attributes. The tuple will be unpacked in the calculate_emission()
      method. The attributes and their types are explained in the constructor.
      The building parameter comes from the calculate_emission() method
      which iterates through the city object buildings.
      :param building: hub.city_model_structure.building.Building
      :return: tuple
    """
    surface_envelope_emission = []
    surface_opening_emission = []
    surface_envelope_end_of_life_emission = []
    surface_opening_end_of_life_emission = []
    opaque_surface_code = self.nrcan_catalogs.find_opaque_surface(
      self.nrcan_catalogs.hub_to_nrcan_function(building.function),
      self.nrcan_catalogs.year_to_period_of_construction(
        building.year_of_construction),
      '6')

    for surface in building.surfaces:
      boundary_envelope_emission = []
      boundary_opening_emission = []
      boundary_envelope_end_of_life_emission = []
      boundary_opening_end_of_life_emission = []

      for boundary in surface.associated_thermal_boundaries:
        opening_emission = None
        opening_end_of_life_emission = None
        layer_emission, layer_end_of_life_emission = \
            self._calculate_envelope_emission(boundary)
        boundary_envelope_emission += layer_emission
        boundary_envelope_end_of_life_emission += layer_end_of_life_emission

        if boundary.window_ratio:
          opening_emission, opening_end_of_life_emission = \
            self._calculate_opening_emission(
              building, surface, boundary, opaque_surface_code)
        if opening_emission:
          boundary_opening_emission += opening_emission
          boundary_opening_end_of_life_emission += opening_end_of_life_emission
      if boundary_opening_emission:
        surface_opening_emission += boundary_opening_emission
        surface_opening_end_of_life_emission += \
            boundary_opening_end_of_life_emission
      surface_envelope_emission += boundary_envelope_emission
      surface_envelope_end_of_life_emission += \
          boundary_envelope_end_of_life_emission
    building_envelope_emission = sum(surface_envelope_emission)
    building_envelope_workload = sum(surface_envelope_end_of_life_emission)
    building_opening_emission = sum(surface_opening_emission)
    building_opening_workload = sum(surface_opening_end_of_life_emission)
    building_component_emission = \
        building_envelope_emission + building_opening_emission
    building_component_workload = \
        building_envelope_workload + building_opening_workload
    return building_envelope_emission, building_opening_emission, \
        building_component_emission, building_envelope_workload, \
        building_opening_workload, building_component_workload

  def _calculate_envelope_emission(self, boundary):
    """
      The method calculates embodied and end of life emission of the building's
      envelope by iterating through each building boundary's layers. The
      argument corresponding to the boundary parameter comes from the
      calculate_building_component_emission() method. The output also is used
      in the calculate_building_component_emission() method. So the current
      method is hidden to the user.
      The method utilizes the EnvelopeEmission and EndOfLifeEmission classes of
      (currently named) life_cycle_assessment series of class.
      :param boundary:
      hub.city_model_structure.building_demand.thermal_boundary.ThermalBoundary
      :return: tuple
    """
    layer_emission = []
    layer_end_of_life_emission = []
    for layer in boundary.layers:
      if not layer.no_mass:
        layer_material = \
         self.nrcan_catalogs.search_material(layer.material_name)
        layer_emission.append(EnvelopeEmission(
          layer_material['embodied_carbon'],
          layer.thickness, 
          boundary.opaque_area,
          layer.density/10).calculate_envelope_emission())

        boundary_workload = \
            boundary.opaque_area * \
            layer.thickness * \
            (layer.density/10)
        layer_end_of_life_emission.append(EndOfLifeEmission(
          layer_material['recycling_ratio'],
          layer_material['onsite_recycling_ratio'],
          layer_material['company_recycling_ratio'],
          layer_material['landfilling_ratio'],
          boundary_workload).calculate_end_of_life_emission())
    return layer_emission, layer_end_of_life_emission

  def _calculate_opening_emission(
          self,
          building, surface, boundary, opaque_surface_code):
    """
      This calculates the opening emission by iterating through each thermal
      opening of each building's boundary. It is done based on the mentioned
      parameters.
      The arguments come from the calculate_building_component_emission()
      method and the output is used in the same method. So the current method
      is hidden to the user.
      Opening workload for the End of Life emission evaluation is based on
      the transparent-surface mass per unit area from the NRCan catalog.
      The method utilizes the OpeningEmission and EndOfLifeEmission classes of
      (currently named) life_cycle_assessment series of class.
      :param building: hub.city_model_structure.building.Building
      :param surface:
      hub.city_model_structure.building_demand.surface.Surface
      :param boundary:
      hub.city_model_structure.building_demand.thermal_boundary.ThermalBoundary
      :param opaque_surface_code: str
      :return: tuple
    """
    opening_emission = []
    opening_end_of_life_emission = []
    for opening in boundary.thermal_openings:
      transparent_surface_type = 'Window'
      if building.year_of_construction >= 2020 and \
              surface.type == 'Roof':
        transparent_surface_type = 'Skylight'
      opening_material = self.nrcan_catalogs.search_transparent_surfaces(
          transparent_surface_type, opaque_surface_code)
      opening_emission.append(
        OpeningEmission(opening_material['embodied_carbon'],
                        opening.area).calculate_opening_emission())

      window_workload = \
          opening.area * opening_material['mass_per_unit unit']
      opening_end_of_life_emission.append(EndOfLifeEmission(
          opening_material['recycling_ratio'],
          opening_material['onsite_recycling_ratio'],
          opening_material['company_recycling_ratio'],
          opening_material['landfilling_ratio'],
          window_workload).calculate_end_of_life_emission())
    return opening_emission, opening_end_of_life_emission

  def calculate_emission(self):
    """
      It iterates through the city object and gives each building to the
      calculate_building_component_emission() method. Then it unpack
      the results of the mentioned method to the (currently six) attributes
      which hold the final results. These attributes are mentioned in the
      constructor method description.
    """
    building_count = 1
    total_buildings = len(self.city.buildings)
    calc_t0 = perf_counter()
    for building in self.city.buildings:
      if (
          building_count == 1
          or building_count == total_buildings
              or building_count % self.progress_log_every == 0):
        pct = (building_count / total_buildings * 100) if total_buildings else 0
        logger.info(
          f'Building emissions progress: {building_count}/{total_buildings} '
          f'({pct:.1f}%)')
      envelope_emission, opening_emission, component_emission, \
          envelope_end_of_life_emission, \
          opening_end_of_life_emission, \
          component_end_of_life_emission = \
          self.calculate_building_component_emission(building)
      self.building_envelope_emission.append(envelope_emission)
      self.building_opening_emission.append(opening_emission)
      self.building_component_emission.append(component_emission)
      self.building_envelope_end_of_life_emission.append(
        envelope_end_of_life_emission)
      self.building_opening_end_of_life_emission.append(
        opening_end_of_life_emission)
      self.building_component_end_of_life_emission.append(
        component_end_of_life_emission)
      building_count += 1
    elapsed_s = perf_counter() - calc_t0
    if total_buildings:
      logger.info(
        'Building emissions calculation completed: '
        f'{total_buildings} buildings in {elapsed_s:.3f}s '
        f'({(elapsed_s / total_buildings) * 1000:.2f} ms/building, '
        f'{(total_buildings / elapsed_s) if elapsed_s else 0:.2f} '
        'buildings/s)')
    else:
      logger.info('Building emissions calculation completed: 0 buildings')
      
  def export_emissions(self):
    """
      This method exports the calculated emissions data as a dictionary 
      of lists corresponding to the input building(s) (the city) geojson file.
      It returns a list of dictionaries, each containing the emissions data
      for a building.
      The keys in the dictionary correspond to the different types of 
      emissions calculated. 
    """
    logger.info(f'Calculated emissions for all buildings are being exported.')
    export_t0 = perf_counter()
    self.calculate_emission()
    emissions = (
        self.building_opening_emission,
        self.building_envelope_emission,
        self.building_component_emission,
        self.building_opening_end_of_life_emission,
        self.building_envelope_end_of_life_emission,
        self.building_component_end_of_life_emission
    )

    num_features = len(emissions[0])  

    emissions_data = []
    for i in range(num_features):
        feature_emissions = {
            'opening_embodied_emissions': emissions[0][i],
            'envelope_embodied_emissions': emissions[1][i],
            'component_embodied_emissions': emissions[2][i],
            'opening_end_of_life_emissions': emissions[3][i],
            'envelope_end_of_life_emissions': emissions[4][i],
            'component_end_of_life_emissions': emissions[5][i]
        }
        emissions_data.append(feature_emissions)

    logger.info(
      f'Emission export payload prepared for {num_features} buildings in '
      f'{perf_counter() - export_t0:.3f}s')
    return emissions_data
