"""
Municipality: Saint-Malachie
handle_mtl_ds_workflow module
The workflow of cleaning and updating the Saint-Malachie Buildings dataset.
Project Developer: Alireza Adli 
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from citygisoo.scrub_layer_class import ScrubLayer
import input_paths_and_layers as paths

# Making folders for the output data layers
paths.create_output_folders(paths.output_paths, paths.output_paths_dir)

property_roll = \
  ScrubLayer(
    paths.qgis_path, paths.input_paths['qc_property_roll_2025'], 'roll')

nrcan = \
  ScrubLayer(paths.qgis_path, paths.input_paths['nrcan_heights'], 'nrcan')

geoindex = \
  ScrubLayer(paths.qgis_path, paths.input_paths['qc_geoindex'], 'geoindex')

fsa = \
  ScrubLayer(paths.qgis_path, paths.input_paths['fsa'], 'fsa')

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
  paths.qgis_path, paths.output_paths['geoindex_fixed'], 'geoindex_fixed')
geoindex_fixed.create_spatial_index()
print(geoindex_fixed)

# There is a step to add here, look at your workflow
# Removing features that do not have provincial id (mostly building-free areas)

# Remove the features
geoindex_fixed.conditional_delete_record(
  'g_id_provi', '=', 'Sans correspondance')

geoindex_fixed.field_join(
    joining_layer_path=paths.input_paths['qc_property_roll_2025'],
    joining_layer_name='roll',
    target_field='g_id_provi',
    join_field='ueid_provinc',
    join_fields=None,
    prefix='rl_',
    output_path=paths.output_paths['geoindex_field_join_roll']
)

# Defining a new layer for the geoindex_field_join_roll
geoindex_field_join_roll = ScrubLayer(
  paths.qgis_path,
  paths.output_paths['geoindex_field_join_roll'], 'geoindex_field_join_roll')
geoindex_field_join_roll.create_spatial_index()
print(geoindex_field_join_roll)

nrcan_fixed.spatial_join(
  geoindex_field_join_roll.layer_path,
  paths.output_paths['nrcan_spatial_join_geoindex'])

nrcan_spatial_join_geoindex = ScrubLayer(
  paths.qgis_path,
  paths.output_paths['nrcan_spatial_join_geoindex'],
  'nrcan_spatial_join_geoindex')

nrcan_spatial_join_geoindex.create_spatial_index()
print(nrcan_spatial_join_geoindex)

nrcan_spatial_join_geoindex.spatial_join(
  fsa.layer_path,
  paths.output_paths['saint_malachie_gisoo_with_fsa'])

saint_malachie_gisoo_with_fsa = ScrubLayer(
  paths.qgis_path,
  paths.output_paths['saint_malachie_gisoo_with_fsa'],
  'saint_malachie_gisoo_with_fsa')

saint_malachie_gisoo_with_fsa.create_spatial_index()
print(saint_malachie_gisoo_with_fsa)

saint_malachie_gisoo_with_fsa.conditional_delete_record(
  'rl_ad_ad_1', 'IS', 'NULL')

# This dataset is already cleaned, but six additional steps will be added
# to optimize the process. Two of them improve the earlier steps.
# The final four steps are listed below, and the required methods to
# carry them out are already available.

# 1 & 2: One feature for one main building. This consists of two steps.
# 3: Remove unnecessary fields.
# 4: Rename the fields.
