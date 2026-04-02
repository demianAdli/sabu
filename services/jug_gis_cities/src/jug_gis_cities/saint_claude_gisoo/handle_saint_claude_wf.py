"""
Municipality: Saint-Claude
handle_mtl_ds_workflow module
The workflow of cleaning and updating the Saint-Claude Buildings dataset.
Project Developer: Alireza Adli 
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from citygisoo.scrub_layer_class import ScrubLayer
from jug_gis_cities.saint_claude_gisoo import input_paths_and_layers as paths

# Making folders for the output data layers
paths.create_output_folders(paths.output_paths, paths.output_paths_dir)

property_roll = \
  ScrubLayer(
    paths.qgis_path, paths.input_paths['qc_property_roll_2025'], 'roll')

nrcan = \
  ScrubLayer(paths.qgis_path, paths.input_paths['nrcan_heights'], 'nrcan')

geoindex = \
  ScrubLayer(paths.qgis_path, paths.input_paths['qc_geoindex'], 'geoindex')

# Processing the NRCan layer includes fixing its geometries
print('Processing the NRCan layer')
print(nrcan)
nrcan.create_spatial_index()
nrcan.fix_geometries(paths.output_paths['nrcan_fixed'])

# Defining a new layer for the fixed NRCan
nrcan_fixed = \
  ScrubLayer(paths.qgis_path, paths.output_paths['nrcan_fixed'], 'nrcan_fixed')
nrcan_fixed.create_spatial_index()
print(nrcan_fixed)

# Processing the geoindex layer includes fixing its geometries
print('Processing the GeoIndex layer')
print(geoindex)
geoindex.create_spatial_index()
geoindex.fix_geometries(paths.output_paths['geoindex_fixed'])

# Defining a new layer for the fixed GeoIndex
geoindex_fixed = ScrubLayer(
  paths.qgis_path, paths.output_paths['Fixed GeoIndex'], 'geoindex_fixed')
geoindex_fixed.create_spatial_index()
print(geoindex_fixed)

