"""
handle_mtl_ds_workflow module
The workflow of cleaning and updating the Montreal Buildings dataset.
Project Developer: Alireza Adli 
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from scrub_layer_class import ScrubLayer
import input_paths_and_layers as paths

# Making folders for the output data layers
paths.create_output_folders(paths.output_paths, paths.output_paths_dir)

# Initialize the input data layers
nrcan = ScrubLayer(paths.qgis_path, paths.input_paths['NRCan'], 'NRCan')
geo_index = ScrubLayer(
  paths.qgis_path, paths.input_paths['GeoIndex'], 'GeoIndex')
property_assessment = \
  ScrubLayer(
    paths.qgis_path,
    paths.input_paths['Property Assessment'],
    'Property Assessment')

montreal_boundary = \
  ScrubLayer(
    paths.qgis_path,
    paths.input_paths['Montreal Boundary'],
    'Montreal Boundary')

# Processing the NRCan layer includes fixing its geometries
print('Processing the NRCan layer')
print(nrcan)
nrcan.create_spatial_index()
nrcan.fix_geometries(paths.output_paths['Fixed NRCan'])

# Defining a new layer for the fixed NRCan
nrcan_fixed = \
  ScrubLayer(paths.qgis_path, paths.output_paths['Fixed NRCan'], 'Fixed NRCan')
nrcan_fixed.create_spatial_index()
print(nrcan_fixed)

# Processing the GeoIndex layer includes fixing its geometries and
# clipping it based on the Montreal boundary data layer
print('Processing the GeoIndex layer')
print(geo_index)
geo_index.create_spatial_index()
geo_index.fix_geometries(paths.output_paths['Fixed GeoIndex'])

# Defining a new layer for the fixed GeoIndex
geo_index_fixed = ScrubLayer(
  paths.qgis_path, paths.output_paths['Fixed GeoIndex'], 'Fixed GeoIndex')
geo_index_fixed.create_spatial_index()
print(geo_index_fixed)
geo_index_fixed.clip_layer(montreal_boundary.layer_path,
                           paths.output_paths['Clipped Fixed GeoIndex'])
geo_index_clipped = \
  ScrubLayer(paths.qgis_path,
             paths.output_paths['Clipped Fixed GeoIndex'],
             'Clipped Fixed GeoIndex')
geo_index_clipped.create_spatial_index()
print(geo_index_clipped)

# Processing the Property Assessment layer includes a pairwise clip, and
# two spatial join with NRCan and GeoIndex layers, respectively

print(property_assessment)
property_assessment.create_spatial_index()

# For the pairwise clip, number of overlaying layers can be chosen
# (meaning number of splits for NRCan layer). This improves the performance
# where may increase duplicates. This has been done because using the NRCan
# layer as a whole causes crashing the clipping process.

# First we split the overlaying layers into our desired number
nrcan_fixed.split_layer(120, paths.output_paths['Splitted NRCans'])

# Clipping have to be done in
clipping_property_assessment = """
from input_paths_and_layers import *

property_assessment.clip_by_multiple(
  120, output_paths['Splitted NRCans'],
  output_paths['Pairwise Clipped Property Assessment Partitions'])"""

exec(clipping_property_assessment)

property_assessment.merge_layers(
  paths.output_paths['Pairwise Clipped Property Assessment Partitions'],
  paths.output_paths['Pairwise Clipped Merged Property Assessment'])

clipped_property_assessment = ScrubLayer(
  paths.qgis_path,
  paths.output_paths['Pairwise Clipped Merged Property Assessment'],
  'Clipped Property Assessment')

print(clipped_property_assessment)
clipped_property_assessment.create_spatial_index()

clipped_property_assessment.spatial_join(
  nrcan_fixed.layer_path,
  paths.output_paths['Property Assessment and NRCan'])

property_assessment_nrcan = ScrubLayer(
  paths.qgis_path,
  paths.output_paths['Property Assessment and NRCan'],
  'Property Assessment and NRCan')

print(property_assessment_nrcan)
property_assessment_nrcan.create_spatial_index()

property_assessment_nrcan.spatial_join(
  geo_index_clipped,
  paths.output_paths['Property Assessment and NRCan and GeoIndex'])

property_assessment_nrcan_geo = ScrubLayer(
  paths.qgis_path,
  paths.output_paths['Property Assessment and NRCan and GeoIndex'],
  'Property Assessment and NRCan and GeoIndex')

print(property_assessment_nrcan_geo)
property_assessment_nrcan_geo.create_spatial_index()

property_assessment_nrcan_geo.delete_duplicates(
  paths.output_paths['Deleted Duplicates Layer'])

deleted_dups_layer = ScrubLayer(
  paths.qgis_path,
  paths.output_paths['Deleted Duplicates Layer'],
  'Deleted Duplicates Layer')

print(deleted_dups_layer)
deleted_dups_layer.create_spatial_index()

deleted_dups_layer.multipart_to_singleparts(
  paths.output_paths['Single Parts Layer'])

single_parts_layer = ScrubLayer(
  paths.qgis_path,
  paths.output_paths['Single Parts Layer'],
  'Single Parts Layer')

print(single_parts_layer)
single_parts_layer.create_spatial_index()

# Add an area field
single_parts_layer.add_field('Area')
single_parts_layer.assign_area('Area')
dismissive_area = 15
single_parts_layer.conditional_delete_record('Area', '<', dismissive_area)

print(
  f'After removing buildings with '
  f'less than {dismissive_area} squaremeter area:')
print(single_parts_layer)
