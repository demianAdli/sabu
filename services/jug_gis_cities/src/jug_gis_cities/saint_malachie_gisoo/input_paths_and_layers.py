"""
Municipality: Saint-Malachie
input_paths_and_layers module
Project Developer: Alireza Adli 
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import os


def create_output_folders(paths_dict, output_dir):
  for path in paths_dict.keys():
    new_folder = path.lower().replace(' ', '_')
    output_path = output_dir + '/' + new_folder
    os.mkdir(output_path)
    if path[-1] != 's':
      paths_dict[path] = output_path + f'/{new_folder}.shp'
    else:
      paths_dict[path] = output_path


# Application's path
qgis_path = 'C:/Program Files/QGIS 3.34.1/apps/qgis'

# Gathering input data layers paths 
input_paths = {
  'qc_property_roll_2025':
  'D:/GIS/saint_malachie_gisoo_data/input_data/'
  'saint_malachie_role_2025_unit_eval_et_address_geopackage/'
  'role_2025_unit_eval_et_address_geopackage_quebec.gpkg',
  'nrcan_heights':
  'D:/GIS/saint_malachie_gisoo_data/input_data/'
  'saint_malachie_auto_with_heights/saint_malachie_auto_with_heights.gpkg',
  'qc_geoindex':
  'D:/GIS/saint_malachie_gisoo_data/input_data/saint_claude_mahm_usage_2025/'
  'mamh_usage_predo_2025_s_poly.shp'
}

# Defining a directory for all the output data layers
output_paths_dir = \
  'C:/Users/a_adli/PycharmProjects/saint_claude/' \
  'output_data'

# Preparing a bedding for output data layers paths
output_paths = {
  'Fixed NRCan': '',
  'NRCan CERC Fixed': '',
  'Fixed GeoIndex': '',
  'Clipped Fixed GeoIndex': '',
  'CERC Property Assessment': '',
  'Splitted CERC NRCans': '',
  'Pairwise Clipped Property Assessment Partitions': '',
  'Pairwise Clipped Merged Property Assessment': '',
  'Property Assessment and NRCan': '',
  'Property Assessment and NRCan and GeoIndex': '',
  'Deleted Duplicates Layer': '',
  'Single Parts Layer': ''
}
